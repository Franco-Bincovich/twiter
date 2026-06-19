"""Middleware de autenticación (SEGURIDAD-PENTEST.md sección 2.1).

Toda ruta que no esté en PUBLIC_ROUTES exige un Bearer token válido. Verifica la
firma con utils/jwt.verify_token y deja el payload en request.state.user. No
verifica ownership del recurso: eso es responsabilidad de cada endpoint (2.4).
"""

from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse

from config.settings import settings
from utils.errors import AppError
from utils.jwt import verify_token
from utils.logger import logger

# Lista blanca explícita y corta. Todo lo demás requiere token verificado.
PUBLIC_ROUTES = [
    "/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
]

# BYPASS DE DESARROLLO — NO DEBE QUEDAR ACTIVO EN PRODUCCIÓN.
# Solo cuando settings.app_env == "development" se permite acceder a las rutas de
# consultas sin token, para habilitar `frontend_prueba` (validación manual de la
# Entrega 1). En cualquier otro entorno (app_env != "development") estas rutas
# siguen exigiendo Bearer válido como cualquier otra. El bypass es SIEMPRE
# condicional al entorno: nunca son públicas de forma permanente.
_DEV_BYPASS_PREFIX = "/consultas"

_UNAUTHORIZED = {"error": True, "message": "No autorizado", "code": "UNAUTHORIZED"}


def _is_dev_bypass(path: str) -> bool:
    """True si la ruta cae en el bypass de consultas y estamos en desarrollo.

    Cubre tanto `/consultas` (POST de creación) como `/consultas/{job_id}` (GET de
    polling). Solo aplica si `settings.app_env == "development"`; en prod devuelve
    siempre False y la ruta queda protegida.
    """
    if settings.app_env != "development":
        return False
    return path == _DEV_BYPASS_PREFIX or path.startswith(f"{_DEV_BYPASS_PREFIX}/")


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

    # Bypass de desarrollo para las rutas de consultas (ver _is_dev_bypass). Nunca
    # se activa en prod: allí estas rutas siguen exigiendo token.
    if _is_dev_bypass(request.url.path):
        logger.warning("Bypass de auth (development)", extra={"path": request.url.path})
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


def get_current_user(request: Request) -> UUID:
    """Dependency: id del usuario autenticado, tomado SIEMPRE del token (§2.4).

    Lee el payload que `auth_middleware` dejó en `request.state.user` y devuelve su
    claim `sub` como UUID tipado. Nunca acepta un id provisto por el cliente: los
    endpoints protegidos operan así solo sobre el dueño del token, garantizando
    ownership sin comparar identificadores externos.

    Args:
        request: Request entrante; debe haber pasado por `auth_middleware`.

    Returns:
        El UUID del usuario autenticado.

    Raises:
        AppError: code 'UNAUTHORIZED' (401), mensaje genérico, si no hay payload o
            no trae un `sub` utilizable.
    """
    payload = getattr(request.state, "user", None)
    if not payload or not payload.get("sub"):
        raise AppError("No autorizado", "UNAUTHORIZED", 401)
    return UUID(payload["sub"])
