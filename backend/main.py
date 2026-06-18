"""Punto de entrada de la app FastAPI: solo configuración, sin lógica de negocio.

Registra el handler global de errores, los middlewares de seguridad (security
headers + CORS) y expone un único endpoint de salud GET /health.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config.settings import settings
from middleware.auth import auth_middleware
from middleware.error_handler import global_error_handler
from routers.auth_router import router as auth_router
from routers.job_router import router as job_router
from routers.me_router import router as me_router
from utils.errors import AppError

app = FastAPI(title="Status Empresarial por CUIT", version="0.1.0")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad a cada respuesta (SEGURIDAD-PENTEST.md 5.1)."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if "server" in response.headers:
            del response.headers["server"]
        return response


# Orden de registro = orden inverso de ejecución (lo último añadido envuelve a lo
# anterior). Se busca este flujo en cada request entrante:
#   CORS → SecurityHeaders → auth → handler
# CORS queda como el más externo para resolver el preflight OPTIONS (sin token)
# antes de que `auth_middleware` exija credenciales. `auth_middleware` deja pasar
# /health y las PUBLIC_ROUTES sin token; todo lo demás requiere Bearer válido.
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_exception_handler(AppError, global_error_handler)
app.add_exception_handler(Exception, global_error_handler)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(job_router)


@app.get("/health")
async def health() -> dict:
    """Endpoint de salud para chequeos de disponibilidad."""
    return {"status": "ok"}
