"""Tests de la capa de autenticación (services/auth_service.py).

Se usa asyncio.run para no depender de plugins async de pytest. Cada test parte de
repos limpios para no acoplarse al estado de los demás. Se verifica especialmente
que los mensajes de error de auth sean genéricos (SEGURIDAD-PENTEST.md 2.3): login
con email inexistente y con password incorrecto devuelven el MISMO error.
"""

import asyncio

import pytest

from repositories.refresh_token_repo import InMemoryRefreshTokenRepository
from repositories.user_repo import InMemoryUserRepository
from services import auth_service
from services.auth_service import (
    login,
    refresh_access_token,
    register,
)
from utils.errors import AppError
from utils.jwt import verify_token

EMAIL = "empresa@ejemplo.com"
PASSWORD = "contraseña-segura-123"


def _reset_repos():
    """Aísla cada test con repositorios en memoria recién creados."""
    auth_service.user_repo = InMemoryUserRepository()
    auth_service.refresh_token_repo = InMemoryRefreshTokenRepository()


def test_register_crea_usuario_y_hashea_el_password():
    _reset_repos()
    asyncio.run(register(EMAIL, PASSWORD))
    user = asyncio.run(auth_service.user_repo.find_by_email(EMAIL))
    assert user is not None
    assert user.password_hash != PASSWORD


def test_register_email_duplicado_falla():
    _reset_repos()
    asyncio.run(register(EMAIL, PASSWORD))
    with pytest.raises(AppError) as exc:
        asyncio.run(register(EMAIL, "otra-password-distinta"))
    assert exc.value.code == "REGISTRATION_FAILED"
    assert exc.value.status_code == 409


def test_login_correcto_devuelve_access_y_refresh():
    _reset_repos()
    asyncio.run(register(EMAIL, PASSWORD))
    tokens = asyncio.run(login(EMAIL, PASSWORD))
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.token_type == "bearer"


def test_login_password_incorrecto_invalid_credentials():
    _reset_repos()
    asyncio.run(register(EMAIL, PASSWORD))
    with pytest.raises(AppError) as exc:
        asyncio.run(login(EMAIL, "password-equivocada"))
    assert exc.value.code == "INVALID_CREDENTIALS"
    assert exc.value.status_code == 401


def test_login_email_inexistente_mismo_error_que_password():
    _reset_repos()
    with pytest.raises(AppError) as exc:
        asyncio.run(login("noexiste@ejemplo.com", PASSWORD))
    # Mismo code y mensaje que el password incorrecto: no se filtra cuál falló.
    assert exc.value.code == "INVALID_CREDENTIALS"
    assert exc.value.message == "Credenciales inválidas"


def test_verify_token_valido_devuelve_payload_con_sub():
    _reset_repos()
    tokens = asyncio.run(register(EMAIL, PASSWORD))
    payload = verify_token(tokens.access_token)
    assert payload["sub"]
    assert payload["type"] == "access"


def test_verify_token_corrupto_invalid_token():
    with pytest.raises(AppError) as exc:
        verify_token("esto.no.es-un-jwt-valido")
    assert exc.value.code == "INVALID_TOKEN"
    assert exc.value.status_code == 401


def test_refresh_rota_el_token_el_viejo_deja_de_valer():
    _reset_repos()
    tokens = asyncio.run(register(EMAIL, PASSWORD))
    viejo = tokens.refresh_token

    nuevos = asyncio.run(refresh_access_token(viejo))
    assert nuevos.refresh_token != viejo

    # Reusar el refresh viejo ya rotado debe fallar (quedó invalidado).
    with pytest.raises(AppError) as exc:
        asyncio.run(refresh_access_token(viejo))
    assert exc.value.status_code == 401
