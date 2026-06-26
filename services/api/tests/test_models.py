from manga_api.models import Asset, GenerationJob, Page, Panel, Project, Render


def test_model_defaults() -> None:
    project = Project(name="Ink Circuit")
    page = Page(project_id=project.id, page_number=1)
    panel = Panel(page_id=page.id, prompt="Hero reveal")
    job = GenerationJob(project_id=project.id, page_id=page.id, panel_id=panel.id)
    asset = Asset(
        project_id=project.id,
        filename="panel.png",
        kind="render",
        content_type="image/png",
        size_bytes=12,
        storage_key="renders/example.png",
    )
    render = Render(
        job_id=job.id,
        panel_id=panel.id,
        asset_id=asset.id,
        storage_key=asset.storage_key,
        width=panel.width,
        height=panel.height,
    )

    assert project.status == "draft"
    assert page.width == 1600
    assert panel.width == 640
    assert job.status == "queued"
    assert job.provider == "mock"
    assert asset.metadata_json == {}
    assert render.mime_type == "image/png"
