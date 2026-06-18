"""Lógica de negocio de autenticación: registro, login, refresh y logout.

Passwords hasheados con bcrypt, nunca en texto plano. Refresh tokens rotados y
guardados hasheados (SEGURIDAD-PENTEST.md 2.5). Mensajes de error siempre
genéricos (2.3): no se filtra si falló el email o el password, ni si el user
existe. El manejo de JWT vive en utils/jwt.py.
"""

import hashlib
from uuid import UUID

from passlib.context import CryptContext

from repositories.refresh_token_repo import (
    InMemoryRefreshTokenRepository,
    RefreshTokenRepository,
)
from repositories.user_repo import InMemoryUserRepository, UserRepository
from schemas.auth import TokenResponse
from utils.errors import AppError
from utils.jwt import create_access_token, create_refresh_token, verify_token
from utils.logger import logger

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Repositorios activos. Temporalmente en memoria; al conectar Supabase se
# reemplazan por las impl Supabase (misma interfaz), sin tocar este service.
user_repo: UserRepository = InMemoryUserRepository()
refresh_token_repo: RefreshTokenRepository = InMemoryRefreshTokenRepository()


def _prepare(secret: str) -> str:
    """Reduce un secreto a un digest SHA-256 hex apto para bcrypt.

    bcrypt trunca su entrada a 72 bytes: un refresh token (JWT de cientos de bytes)
    o un password largo perderían los bytes finales, donde justamente difieren. El
    digest hex (64 chars ASCII, sin bytes nulos) condensa el secreto completo y
    queda dentro del límite, preservando toda su entropía.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _hash_secret(secret: str) -> str:
    """Devuelve el hash bcrypt de un secreto (password o refresh token)."""
    return _pwd_context.hash(_prepare(secret))


def _verify_secret(secret: str, secret_hash: str) -> bool:
    """Verifica un secreto contra su hash bcrypt, sin lanzar ante hash inválido."""
    try:
        return _pwd_context.verify(_prepare(secret), secret_hash)
    except ValueError:
        return False


async def register(email: str, password: str) -> TokenResponse:
    """Registra un usuario nuevo y emite su par de tokens inicial.

    Args:
        email: Email del usuario, ya validado por el schema de entrada.
        password: Password en texto plano; se hashea con bcrypt antes de guardar.

    Returns:
        TokenResponse con access y refresh tokens recién emitidos.

    Raises:
        AppError: code 'REGISTRATION_FAILED' (409), mensaje genérico, si el email
            ya existe (no se confirma la existencia previa del usuario).
    """
    if await user_repo.find_by_email(email) is not None:
        raise AppError("No se pudo completar el registro", "REGISTRATION_FAILED", 409)
    user = await user_repo.create(email, _hash_secret(password))
    logger.info("Usuario registrado", extra={"user_id": str(user.id)})
    return await _emitir_tokens(user.id)


async def login(email: str, password: str) -> TokenResponse:
    """Verifica credenciales y emite un par de tokens nuevo.

    Args:
        email: Email del usuario.
        password: Password en texto plano a verificar contra el hash guardado.

    Returns:
        TokenResponse con access y refresh tokens recién emitidos.

    Raises:
        AppError: code 'INVALID_CREDENTIALS' (401), mismo mensaje genérico tanto
            si el email no existe como si el password no coincide (no se filtra
            cuál de los dos falló).
    """
    user = await user_repo.find_by_email(email)
    if user is None or not _verify_secret(password, user.password_hash):
        logger.warning("Login fallido", extra={"email": email})
        raise AppError("Credenciales inválidas", "INVALID_CREDENTIALS", 401)
    await user_repo.update_last_login(user.id)
    logger.info("Login exitoso", extra={"user_id": str(user.id)})
    return await _emitir_tokens(user.id)


async def refresh_access_token(refresh_token: str) -> TokenResponse:
    """Rota el refresh token: valida el actual, lo invalida y emite uno nuevo.

    Args:
        refresh_token: Refresh token en texto plano enviado por el cliente.

    Returns:
        TokenResponse con un par de tokens nuevo; el refresh anterior queda invalidado.

    Raises:
        AppError: code 'INVALID_TOKEN' (401) si el token no es válido o no es de
            tipo refresh; code 'UNAUTHORIZED' (401) si no coincide con el hash
            guardado. Mensajes genéricos en ambos casos.
    """
    payload = verify_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AppError("No autorizado", "INVALID_TOKEN", 401)
    user_id = UUID(payload["sub"])
    stored = await refresh_token_repo.find_by_user(user_id)
    if stored is None or not _verify_secret(refresh_token, stored.token_hash):
        raise AppError("No autorizado", "UNAUTHORIZED", 401)
    await refresh_token_repo.delete(stored.id)
    return await _emitir_tokens(user_id)


async def logout(user_id: UUID) -> None:
    """Cierra la sesión borrando el refresh token guardado del usuario.

    Args:
        user_id: Identificador del usuario cuya sesión se cierra.
    """
    stored = await refresh_token_repo.find_by_user(user_id)
    if stored is not None:
        await refresh_token_repo.delete(stored.id)


async def _emitir_tokens(user_id: UUID) -> TokenResponse:
    """Emite access + refresh y persiste el refresh hasheado para el usuario.

    Args:
        user_id: Identificador del usuario al que se le emiten los tokens.

    Returns:
        TokenResponse con el par recién emitido.
    """
    sub = str(user_id)
    access = create_access_token(sub)
    refresh = create_refresh_token(sub)
    await refresh_token_repo.save(user_id, _hash_secret(refresh))
    return TokenResponse(access_token=access, refresh_token=refresh)
