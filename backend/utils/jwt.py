"""Creación y verificación de JWT (SEGURIDAD-PENTEST.md sección 2.2 y 2.3).

Tokens tipados ('access' / 'refresh') para que un refresh no pueda usarse como
access. Los mensajes de error de verificación son siempre genéricos (sección 2.3):
no revelan si el token expiró, está corrupto o el usuario no existe.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt

from config.settings import settings
from utils.errors import AppError

ALGORITHM = "HS256"


def create_access_token(user_id: str) -> str:
    """Emite un access token JWT de corta duración para un usuario.

    Args:
        user_id: Identificador del usuario (claim 'sub'), como string.

    Returns:
        El JWT firmado con HS256, con claims sub/exp/iat y type='access'.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expiration_minutes
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Emite un refresh token JWT de larga duración para un usuario.

    Args:
        user_id: Identificador del usuario (claim 'sub'), como string.

    Returns:
        El JWT firmado con HS256, con claims sub/exp/iat, type='refresh' y un jti
        único. El jti garantiza que dos refresh tokens del mismo usuario emitidos
        en el mismo segundo sean distintos, condición necesaria para que la
        rotación (invalidar el anterior) funcione.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expiration_days
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Decodifica y valida un JWT (firma y expiración).

    Args:
        token: El JWT a verificar.

    Returns:
        El payload decodificado como dict.

    Raises:
        AppError: code 'INVALID_TOKEN' (401), mensaje genérico, ante cualquier
            fallo de validación (firma inválida, expirado, malformado).
    """
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise AppError("No autorizado", "INVALID_TOKEN", 401)
