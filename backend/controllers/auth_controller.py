"""Orquestación de autenticación y del shell de onboarding entre router y service.

Sin lógica de negocio propia: delega en `auth_service` (la lógica de seguridad ya
existente) y, para el usuario actual / onboarding, en el repositorio de usuarios. La
identidad usada es SIEMPRE la del token (§2.4); ningún id llega desde el cliente.
"""

from uuid import UUID

from schemas.auth import LoginRequest, MeResponse, RefreshRequest, RegisterRequest, TokenResponse
from services import auth_service
from services.auth_service import login, logout, refresh_access_token, register
from utils.errors import AppError
from utils.logger import logger


async def register_controller(payload: RegisterRequest) -> TokenResponse:
    """Registra un usuario nuevo y devuelve su par de tokens inicial."""
    return await register(payload.email, payload.password)


async def login_controller(payload: LoginRequest) -> TokenResponse:
    """Verifica credenciales y devuelve un par de tokens nuevo."""
    return await login(payload.email, payload.password)


async def refresh_controller(payload: RefreshRequest) -> TokenResponse:
    """Rota el refresh token recibido y devuelve un par de tokens nuevo."""
    return await refresh_access_token(payload.refresh_token)


async def logout_controller(user_id: UUID) -> None:
    """Cierra la sesión del usuario del token, borrando su refresh token."""
    await logout(user_id)
    logger.info("Logout exitoso", extra={"user_id": str(user_id)})


async def get_me_controller(user_id: UUID) -> MeResponse:
    """Devuelve los datos públicos del usuario del token (nunca un id del cliente)."""
    user = await auth_service.user_repo.find_by_id(user_id)
    if user is None:
        raise AppError("No autorizado", "UNAUTHORIZED", 401)
    return MeResponse(
        id=user.id, email=user.email, onboarding_completed=user.onboarding_completed
    )


async def complete_onboarding_controller(user_id: UUID) -> MeResponse:
    """Marca onboarding_completed=True para el usuario del token y lo devuelve."""
    await auth_service.user_repo.update_onboarding_completed(user_id)
    return await get_me_controller(user_id)
