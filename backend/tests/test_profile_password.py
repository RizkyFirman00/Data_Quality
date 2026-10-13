import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import TEST_PASSWORD, TEST_USERNAME


NEW_PASSWORD = "password-baru-aman-123"


def payload(**overrides):
    return {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD, **overrides}


def test_change_password_revokes_all_sessions_and_requires_new_password(client):
    with TestClient(app) as other:
        assert other.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}).status_code == 200
        response = client.post("/api/auth/password", json=payload())
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert NEW_PASSWORD not in response.text
        assert TEST_PASSWORD not in response.text
        assert client.get("/api/auth/me").status_code == 401
        assert other.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}).status_code == 401
    login = client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": NEW_PASSWORD})
    assert login.status_code == 200
    assert login.json()["user"]["is_admin"] is True


@pytest.mark.parametrize("changes,status", [
    ({"current_password": "password-salah"}, 400),
    ({"confirm_password": "konfirmasi-tidak-sama"}, 422),
    ({"new_password": TEST_PASSWORD, "confirm_password": TEST_PASSWORD}, 422),
    ({"new_password": "short", "confirm_password": "short"}, 422),
    ({"username": "other-user"}, 422),
    ({"is_admin": True}, 422),
])
def test_rejected_change_preserves_password_and_session(client, changes, status):
    response = client.post("/api/auth/password", json=payload(**changes))
    assert response.status_code == status
    assert TEST_PASSWORD not in response.text
    assert NEW_PASSWORD not in response.text
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}).status_code == 200


def test_password_verification_locks_after_repeated_failures(client):
    for _ in range(5):
        assert client.post("/api/auth/password", json=payload(current_password="wrong")).status_code == 400
    response = client.post("/api/auth/password", json=payload())
    assert response.status_code == 400
    assert "terkunci" in response.json()["detail"]["message"]


def test_change_requires_csrf(client):
    del client.headers["x-csrf-token"]
    assert client.post("/api/auth/password", json=payload()).status_code == 403


def test_change_requires_login(client):
    client.cookies.clear()
    assert client.post("/api/auth/password", json=payload()).status_code == 401


@pytest.mark.parametrize("role", ["Admin", "Pemeriksa"])
def test_new_account_can_change_initial_password_without_changing_role(client, role):
    assert client.post("/api/users", json={"username": "new.user", "display_name": "Pengguna Baru", "role": role}).status_code == 201
    login = client.post("/api/auth/login", json={"username": "new.user", "password": "Password123"})
    client.headers["x-csrf-token"] = login.json()["csrf_token"]
    assert client.post("/api/auth/password", json=payload(current_password="Password123")).status_code == 200
    login = client.post("/api/auth/login", json={"username": "new.user", "password": NEW_PASSWORD})
    assert login.status_code == 200
    assert login.json()["user"]["is_admin"] is (role == "Admin")
    assert client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}).status_code == 200
