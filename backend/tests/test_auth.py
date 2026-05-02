from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_auth_service
from backend.app.main import app
from backend.app.repositories.in_memory import InMemoryUserRepository
from backend.app.services.auth import AuthError, AuthService, verify_password


def _auth_service() -> AuthService:
    return AuthService(InMemoryUserRepository(), "test-session-secret", 3600)


def test_auth_service_registers_with_hash_and_free_plan() -> None:
    service = _auth_service()

    user = service.register("User@Example.com", "analyst", "Securepass123")

    assert user.gmail == "user@example.com"
    assert user.nombre == "analyst"
    assert user.plan == "free"
    assert user.password_hash != "Securepass123"
    assert verify_password("Securepass123", user.password_hash)


def test_auth_service_rejects_duplicate_gmail_and_weak_password() -> None:
    service = _auth_service()
    service.register("user@example.com", "analyst", "Securepass123")

    try:
        service.register("USER@example.com", "other", "Securepass123")
    except AuthError as exc:
        assert "Ya existe" in str(exc)
    else:
        raise AssertionError("duplicate gmail was accepted")

    try:
        service.register("new@example.com", "other", "short")
    except AuthError as exc:
        assert "10 caracteres" in str(exc)
    else:
        raise AssertionError("weak password was accepted")


def test_web_register_login_account_and_logout_flow() -> None:
    service = _auth_service()
    app.dependency_overrides[get_auth_service] = lambda: service
    client = TestClient(app)
    try:
        register_response = client.post(
            "/register",
            data={"gmail": "user@example.com", "nombre": "analyst", "password": "Securepass123"},
            follow_redirects=False,
        )
        assert register_response.status_code == 303
        assert "gordon_session" in register_response.cookies

        account_response = client.get("/account")
        assert account_response.status_code == 200
        assert "user@example.com" in account_response.text
        assert "free" in account_response.text

        csrf = service.read_session(client.cookies.get("gordon_session")).csrf_token
        profile_response = client.post("/account/profile", data={"csrf_token": csrf, "nombre": "quant"})
        assert profile_response.status_code == 200
        assert service.current_user(client.cookies.get("gordon_session")).nombre == "quant"

        logout_response = client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)
        assert logout_response.status_code == 303
    finally:
        app.dependency_overrides.pop(get_auth_service, None)
