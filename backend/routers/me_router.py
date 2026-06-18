"""Endpoints del usuario actual y del shell de onboarding. Sin lógica de negocio.

Ambas rutas (`/api/me`, `/api/onboarding/complete`) quedan fuera de PUBLIC_ROUTES,
por lo que `auth_middleware` exige Bearer token. La identidad se resuelve siempre
desde el token vía `get_current_user` (§2.4), nunca desde el cuerpo del request.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from controllers.auth_controller import (
    complete_onboarding_controller,
    get_me_controller,
)
from middleware.auth import get_current_user
from schemas.auth import MeResponse

router = APIRouter(prefix="/api", tags=["onboarding"])


@router.get("/me", response_model=MeResponse)
async def get_me_endpoint(user_id: UUID = Depends(get_current_user)) -> MeResponse:
    return await get_me_controller(user_id)


@router.post("/onboarding/complete", response_model=MeResponse)
async def complete_onboarding_endpoint(
    user_id: UUID = Depends(get_current_user),
) -> MeResponse:
    return await complete_onboarding_controller(user_id)
