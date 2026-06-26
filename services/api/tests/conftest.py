import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENABLE_BACKGROUND_JOBS"] = "false"

from manga_api.db import get_session  # noqa: E402
from manga_api.main import app  # noqa: E402
from manga_api import models  # noqa: E402,F401
from manga_api.storage import get_object_storage  # noqa: E402


class MemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key][0]

    def public_url(self, key: str) -> str:
        return f"http://objects.test/{key}"

    def check(self) -> None:
        return None


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    storage = MemoryObjectStorage()
    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.state.engine = engine
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    SQLModel.metadata.drop_all(engine)
