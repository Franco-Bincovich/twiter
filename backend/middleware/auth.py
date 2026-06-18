"""Middleware de autenticación (SEGURIDAD-PENTEST.md sección 2.1).

Toda ruta que no esté en PUBLIC_ROUTES exige un Bearer token válido. Verifica la
firma con utils/jwt.verify_token y deja el payload en request.state.user. No
verifica ownership del recurso: eso es responsabilidad de cada endpoint (2.4).
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from utils.jwt import verify_token
from utils.logger import logger

# Lista blanca explícita y corta. Todo lo demás requiere token verificado.
PUBLIC_ROUTES = [
    "/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
]

_UNAUTHORIZED = {"error": True, "message": "No autorizado", "code": "UNAUTHORIZED"}


async def auth_middleware(request: Request, call_next):
    """Exige y valida el Bearer token salvo en las rutas públicas.

    Args:
        request: Request entrante de Starlette/FastAPI.
        call_next: Siguiente handler de la cadena de middlewares.

    Returns:
        La respuesta del handler si el token es válido o la ruta es pública; un
        401 genérico si falta el token o no se puede verificar.
    """
    if request.url.path in PUBLIC_ROUTES:
        return await call_next(request)

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        logger.warning("Token ausente", extra={"path": request.url.path})
        return JSONResponse(status_code=401, content=_UNAUTHORIZED)

    try:
        request.state.user = verify_token(token)
    except Exception:
        logger.warning("Token inválido", extra={"path": request.url.path})
        return JSONResponse(status_code=401, content=_UNAUTHORIZED)

    return await call_next(request)
