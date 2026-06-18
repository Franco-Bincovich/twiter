"""Schemas Pydantic de autenticación (frontera de entrada/salida) y entidad User.

Pydantic estricto: los payloads de registro y login validan formato de email y
longitud mínima de password antes de llegar a la lógica de negocio.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload de registro de un usuario nuevo."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Payload de inicio de sesión."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Par de tokens emitido tras un login o un refresh exitoso."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class User(BaseModel):
    """Entidad de dominio del usuario, tal como se persiste y circula entre capas.

    El password nunca se guarda en texto plano: solo se conserva su hash bcrypt.
    """

    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    password_hash: str
    onboarding_completed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
