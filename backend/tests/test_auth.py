from fastapi.testclient import TestClient

from conftest import TEST_PASSWORD, TEST_USERNAME


def test_authenticated_session_returns_only_safe_user_fields(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": body["user"]["id"],
        "username": TEST_USERNAME,
        "display_name": "Reviewer Test",
        "is_admin": True,
    }
    assert len(body["csrf_token"]) >= 32
    assert "password" not in str(body).lower()


def test_protected_api_requires_login_but_health_remains_public(client: TestClient) -> None:
    client.cookies.clear()

    protected = client.get("/api/datasets")
    docs = client.get("/docs")
    health = client.get("/api/health")

    assert protected.status_code == 401
    assert docs.status_code == 401
    assert protected.json()["detail"]["message"] == "Sesi login diperlukan."
    assert health.status_code == 200


def test_login_sets_http_only_cookie_and_logout_revokes_session(client: TestClient) -> None:
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME.upper(), "password": TEST_PASSWORD},
    )

    assert login.status_code == 200
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert login.headers["cache-control"] == "no-store"
    csrf_token = login.json()["csrf_token"]
    client.headers["x-csrf-token"] = csrf_token

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_error_does_not_reveal_whether_username_exists(client: TestClient) -> None:
    client.cookies.clear()

    known = client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": "salah"})
    unknown = client.post("/api/auth/login", json={"username": "unknown", "password": "salah"})

    assert known.status_code == unknown.status_code == 401
    assert known.json()["detail"]["message"] == unknown.json()["detail"]["message"]


def test_account_is_temporarily_locked_after_failed_attempt_limit(client: TestClient) -> None:
    client.cookies.clear()
    for _ in range(5):
        assert client.post(
            "/api/auth/login", json={"username": TEST_USERNAME, "password": "salah"}
        ).status_code == 401

    correct = client.post(
        "/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )

    assert correct.status_code == 401
    assert correct.json()["detail"]["message"] == "Username atau password tidak valid."


def test_mutating_request_requires_csrf_token(client: TestClient) -> None:
    del client.headers["x-csrf-token"]

    response = client.post("/api/backoffice-assessments")

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "Token keamanan permintaan tidak valid."
