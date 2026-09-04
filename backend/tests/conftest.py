from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.auth import PASSWORD_HASH, create_local_session
from app.database import get_session
from app.main import app
from app.models import Base, LocalUser


TEST_USERNAME = "reviewer"
TEST_PASSWORD = "password-test-yang-kuat"
TEST_PASSWORD_HASH = PASSWORD_HASH.hash(TEST_PASSWORD)


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    config = Settings(
        database_url="sqlite://",
        storage_root=tmp_path / "storage",
        max_upload_mb=1,
        preview_rows=2,
        cors_origins=("http://localhost:5173",),
    )

    with Session(engine, expire_on_commit=False) as setup_session:
        user = LocalUser(
            username=TEST_USERNAME,
            display_name="Reviewer Test",
            password_hash=TEST_PASSWORD_HASH,
            is_admin=True,
        )
        setup_session.add(user)
        setup_session.commit()
        auth_session, token = create_local_session(setup_session, user, config)

    def session_override() -> Generator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: config
    with TestClient(app) as test_client:
        test_client.cookies.set(config.auth_cookie_name, token)
        test_client.headers.update({"x-csrf-token": auth_session.csrf_token})
        yield test_client
    app.dependency_overrides.clear()
