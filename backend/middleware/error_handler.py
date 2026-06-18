"""Handler global de errores (ver ORDEN-Y-LEGIBILIDAD.md sección 7).

Un único lugar captura todas las excepciones y las traduce al formato de error
estándar del proyecto: {"error": True, "message": ..., "code": ...}.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from utils.errors import AppError
from utils.logger import logger


async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Traduce cualquier excepción a una respuesta de error con formato uniforme.

    Args:
        request: Request entrante; se usa solo para registrar la ruta afectada.
        exc: Excepción capturada. Si es AppError respeta su status y code;
            cualquier otra excepción se reporta como 500 INTERNAL_ERROR sin
            filtrar detalle interno al cliente.

    Returns:
        JSONResponse con el cuerpo {"error": True, "message": ..., "code": ...}.
    """
    if isinstance(exc, AppError):
        logger.warning(exc.message, extra={"code": exc.code, "path": request.url.path})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": True, "message": exc.message, "code": exc.code},
        )

    logger.error("Error inesperado", extra={"error": str(exc), "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Error interno del servidor",
            "code": "INTERNAL_ERROR",
        },
    )
