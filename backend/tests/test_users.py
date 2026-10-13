import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import INITIAL_ACCOUNT_PASSWORD, PASSWORD_HASH, validate_password
from app.database import get_session
from app.main import app
from app.models import LocalUser


@pytest.mark.parametrize("role", ["Admin", "Pemeriksa"])
def test_admin_creates_account_with_hashed_default_password(client: TestClient, role):
    response = client.post("/api/users", json={"username": " New.User ", "display_name": " Pengguna Baru ", "role": role})
    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "username": "new.user", "display_name": "Pengguna Baru", "role": role, "is_active": True}
    assert response.headers["cache-control"] == "no-store"
    generator = app.dependency_overrides[get_session]()
    try:
        session = next(generator)
        user = session.scalar(select(LocalUser).where(LocalUser.username == "new.user"))
        assert user.password_hash != INITIAL_ACCOUNT_PASSWORD
        assert PASSWORD_HASH.verify(INITIAL_ACCOUNT_PASSWORD, user.password_hash)
        assert user.is_admin is (role == "Admin")
    finally:
        generator.close()
    accounts = client.get("/api/users")
    assert accounts.status_code == 200
    assert body in accounts.json()
    assert "password" not in accounts.text.lower()
    login = client.post("/api/auth/login", json={"username": "new.user", "password": "Password123"})
    assert login.status_code == 200
    assert login.json()["user"]["is_admin"] is (role == "Admin")
    client.headers["x-csrf-token"] = login.json()["csrf_token"]
    assert client.get("/api/datasets").status_code == 200
    assert client.get("/api/users").status_code == (200 if role == "Admin" else 403)
    if role == "Pemeriksa":
        denied = client.post("/api/users", json={"username": "escalated", "display_name": "Not Allowed", "role": "Admin"})
        assert denied.status_code == 403


def test_duplicate_username_is_case_insensitive(client: TestClient):
    payload = {"username": "new.user", "display_name": "Nama"}
    assert client.post("/api/users", json=payload).status_code == 201
    assert client.post("/api/users", json={**payload, "username": "NEW.USER"}).status_code == 409


@pytest.mark.parametrize("payload", [
    {"username": "invalid space", "display_name": "Nama"},
    {"username": "new.user", "display_name": "   "},
    {"username": "ab", "display_name": "Nama"},
    {"username": "new.user", "display_name": "Nama", "role": "Owner"},
    {"username": "new.user", "display_name": "Nama", "password": "override-password"},
    {"username": "new.user", "display_name": "Nama", "is_admin": True},
])
def test_invalid_account_input_does_not_create_user(client: TestClient, payload):
    before = client.get("/api/users").json()
    assert client.post("/api/users", json=payload).status_code == 422
    assert client.get("/api/users").json() == before


def test_account_creation_requires_csrf(client: TestClient):
    del client.headers["x-csrf-token"]
    assert client.post("/api/users", json={"username": "new.user", "display_name": "Nama"}).status_code == 403


def test_accounts_require_authentication(client: TestClient):
    client.cookies.clear()
    assert client.get("/api/users").status_code == 401
    assert client.post("/api/users", json={"username": "new.user", "display_name": "Nama"}).status_code == 401


def test_initial_password_exception_does_not_weaken_password_change_policy():
    with pytest.raises(ValueError):
        validate_password("Password123")
