from io import BytesIO

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from manga_api.compositor import PageCompositor
from manga_api.main import app
from manga_api.models import Asset, Bubble, GenerationJob, Page, Panel, Project, Render
from manga_api.rendering import MockImageProvider
from manga_api.storage import get_object_storage


class MemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key][0]

    def public_url(self, key: str) -> str:
        return f"http://objects.test/{key}"


def test_compose_page_with_mock_panel_renders_outputs_page_dimensions() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    storage = MemoryObjectStorage()

    with Session(engine) as session:
        project = Project(name="Composite Project")
        page = Page(
            project_id=project.id,
            page_number=1,
            width=800,
            height=1200,
            layout_json={"reading_direction": "rtl", "bleed": 24, "safe_margin": 64},
        )
        panel_a = Panel(
            page_id=page.id,
            x=60,
            y=80,
            width=300,
            height=260,
            reading_order=1,
            polygon=[
                {"x": 60, "y": 80},
                {"x": 360, "y": 80},
                {"x": 360, "y": 340},
                {"x": 60, "y": 340},
            ],
        )
        panel_b = Panel(
            page_id=page.id,
            x=410,
            y=80,
            width=300,
            height=260,
            reading_order=2,
            polygon=[
                {"x": 410, "y": 80},
                {"x": 710, "y": 80},
                {"x": 710, "y": 340},
                {"x": 410, "y": 340},
            ],
        )
        session.add_all([project, page, panel_a, panel_b])
        session.commit()

        for panel in [panel_a, panel_b]:
            add_mock_render(session, storage, project, page, panel)

        session.add_all(
            [
                Bubble(panel_id=panel_a.id, kind="speech", x=96, y=110, width=210, height=110, text="We move now."),
                Bubble(panel_id=panel_b.id, kind="thought", x=452, y=116, width=210, height=120, text="Too quiet."),
                Bubble(panel_id=panel_a.id, kind="narration", x=90, y=380, width=260, height=80, text="Night settles over the rooftops."),
                Bubble(panel_id=panel_b.id, kind="shout", x=430, y=390, width=240, height=110, text="Run!"),
            ]
        )
        session.commit()

        result = PageCompositor(session, storage).compose_page(page.id)

        assert result.asset.kind == "page_composite"
        assert result.asset.storage_key in storage.objects
        assert result.asset.metadata_json["reading_direction"] == "rtl"
        image = Image.open(BytesIO(storage.objects[result.asset.storage_key][0]))
        assert image.size == (800, 1200)
        stored_asset = session.exec(select(Asset).where(Asset.id == result.asset.id)).one()
        assert stored_asset.size_bytes > 0

    SQLModel.metadata.drop_all(engine)


def test_compose_page_endpoint_returns_latest_composite(client) -> None:
    storage = MemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    try:
        project = client.post("/projects", json={"name": "Endpoint Composite"}).json()
        page = client.post(f"/projects/{project['id']}/pages", json={"width": 640, "height": 960}).json()
        layout_response = client.put(
            f"/pages/{page['id']}/layout",
            json={
                "width": 640,
                "height": 960,
                "bleed": 16,
                "safe_margin": 48,
                "reading_direction": "ltr",
                "qa_overlay_enabled": False,
                "panels": [
                    {
                        "x": 60,
                        "y": 80,
                        "width": 260,
                        "height": 220,
                        "reading_order": 1,
                        "prompt": "Panel one",
                        "polygon": [
                            {"x": 60, "y": 80},
                            {"x": 320, "y": 80},
                            {"x": 320, "y": 300},
                            {"x": 60, "y": 300},
                        ],
                    }
                ],
            },
        )
        panel = layout_response.json()["panels"][0]
        client.post(
            f"/panels/{panel['id']}/bubbles",
            json={"kind": "shout", "x": 90, "y": 120, "width": 180, "height": 100, "text": "Go!"},
        )

        compose_response = client.post(f"/pages/{page['id']}/compose")
        assert compose_response.status_code == 201
        composite = compose_response.json()
        assert composite["width"] == 640
        assert composite["height"] == 960
        assert composite["reading_direction"] == "ltr"
        assert composite["storage_key"] in storage.objects
        output = Image.open(BytesIO(storage.objects[composite["storage_key"]][0]))
        assert output.size == (640, 960)

        latest_response = client.get(f"/pages/{page['id']}/composite")
        assert latest_response.status_code == 200
        assert latest_response.json()["id"] == composite["id"]
    finally:
        app.dependency_overrides.pop(get_object_storage, None)


def add_mock_render(
    session: Session,
    storage: MemoryObjectStorage,
    project: Project,
    page: Page,
    panel: Panel,
) -> None:
    provider = MockImageProvider()
    generated = provider.generate_image(
        f"Panel {panel.reading_order}",
        f"{panel.width}x{panel.height}",
        [],
        {"seed": panel.reading_order, "panel_id": str(panel.id)},
    )
    key = f"renders/{project.id}/{panel.id}.png"
    storage.put_bytes(key=key, data=generated.data, content_type=generated.content_type)
    job = GenerationJob(
        project_id=project.id,
        page_id=page.id,
        panel_id=panel.id,
        provider="mock",
        job_type="render_panel",
        status="succeeded",
        input_payload={"panel_id": str(panel.id)},
        output_payload={"storage_key": key},
    )
    session.add(job)
    session.flush()
    asset = Asset(
        project_id=project.id,
        filename=f"panel-{panel.id}.png",
        kind="render",
        content_type=generated.content_type,
        size_bytes=len(generated.data),
        storage_key=key,
        metadata_json={"panel_id": str(panel.id)},
    )
    session.add(asset)
    session.flush()
    session.add(
        Render(
            job_id=job.id,
            panel_id=panel.id,
            asset_id=asset.id,
            storage_key=key,
            public_url=storage.public_url(key),
            width=generated.width,
            height=generated.height,
            mime_type=generated.content_type,
        )
    )
    session.commit()
