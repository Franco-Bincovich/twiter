"""Tests de los endpoints de autenticación y del shell de onboarding.

Se usa el TestClient de FastAPI (un único proceso, repos en memoria). Cada test
parte de repositorios limpios para no acoplarse al estado de los demás. Se valida
especialmente que /health y las rutas públicas pasen el middleware sin token, y
que /api/me y onboarding operen sobre el usuario del token (§2.4), nunca sobre un
id provisto por el cliente.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories.refresh_token_repo import InMemoryRefreshTokenRepository
from repositories.user_repo import InMemoryUserRepository
from services import auth_service

EMAIL = "empresa@ejemplo.com"
PASSWORD = "contraseña-segura-123"


@pytest.fixture
def client():
    """TestClient con repos en memoria recién creados para aislar cada test."""
    auth_service.user_repo = InMemoryUserRepository()
    auth_service.refresh_token_repo = InMemoryRefreshTokenRepository()
    return TestClient(app)


def _registrar(client) -> dict:
    """Registra el usuario de prueba y devuelve el cuerpo con los tokens."""
    resp = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert resp.status_code == 201
    return resp.json()


def test_register_devuelve_201(client):
    resp = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert resp.status_code == 201
    assert resp.json()["access_token"]


def test_login_correcto_devuelve_200_con_tokens(client):
    _registrar(client)
    resp = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]


def test_me_sin_token_devuelve_401(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_me_con_token_valido_devuelve_datos_del_user(client):
    tokens = _registrar(client)
    resp = client.get(
        "/api/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["onboarding_completed"] is False
    assert body["id"]


def test_health_sin_token_sigue_siendo_publica(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_onboarding_complete_pone_onboarding_en_true(client):
    tokens = _registrar(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.post("/api/onboarding/complete", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["onboarding_completed"] is True
    # Persiste: una nueva consulta a /api/me lo refleja.
    me = client.get("/api/me", headers=headers)
    assert me.json()["onboarding_completed"] is True


def test_refresh_devuelve_tokens_nuevos(client):
    tokens = _registrar(client)
    resp = client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"] != tokens["refresh_token"]
