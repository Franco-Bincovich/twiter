"""Endpoints de autenticación. Sin lógica de negocio.

Las rutas públicas (register/login/refresh) coinciden EXACTO con PUBLIC_ROUTES de
middleware/auth.py. `logout` no es pública: exige Bearer token y opera sobre el
usuario del token vía la dependency `get_current_user`.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from controllers.auth_controller import (
    login_controller,
    logout_controller,
    refresh_controller,
    register_controller,
)
from middleware.auth import get_current_user
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse
)
async def register_endpoint(payload: RegisterRequest) -> TokenResponse:
    return await register_controller(payload)


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(payload: LoginRequest) -> TokenResponse:
    return await login_controller(payload)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_endpoint(payload: RefreshRequest) -> TokenResponse:
    return await refresh_controller(payload)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_endpoint(user_id: UUID = Depends(get_current_user)) -> None:
    await logout_controller(user_id)
