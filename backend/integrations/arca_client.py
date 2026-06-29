"""Cliente HTTP de cuitonline.com (wrapper de transporte del Agente ARCA).

Aísla TODA llamada a cuitonline (§6.2: request/reintentos/rate limit/headers); arma la URL
del detalle desde el CUIT + razón social y delega el parseo del HTML en `arca_parser`.
"""

import asyncio
import re
import time
import unicodedata

import httpx

from integrations import arca_parser
from utils.errors import AppError
from utils.logger import logger

_BASE_URL = "https://www.cuitonline.com"
_TIMEOUT_SEG = 15.0
_MAX_INTENTOS = 3
_BACKOFF_BASE_SEG = 1.0      # espera = base * 2**(intento-1): 1s, 2s, 4s
_RATE_LIMIT_SEG = 1.0        # mínimo entre requests al mismo host (anti-bloqueo)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_ultimo_request: float = 0.0
_rate_lock = asyncio.Lock()


async def _rate_limit() -> None:
    """Serializa los requests dejando al menos _RATE_LIMIT_SEG entre llamadas al host."""
    global _ultimo_request
    async with _rate_lock:
        espera = _RATE_LIMIT_SEG - (time.monotonic() - _ultimo_request)
        if espera > 0:
            await asyncio.sleep(espera)
        _ultimo_request = time.monotonic()


async def _get(url: str) -> httpx.Response | None:
    """GET con headers, rate limit y reintentos (backoff exp.); None si la fuente da 404.

    429/403 → 'ARCA_RATE_LIMITED' (503); caída tras los reintentos → 'ARCA_UNAVAILABLE' (503).
    """
    for intento in range(1, _MAX_INTENTOS + 1):
        await _rate_limit()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SEG, headers=_HEADERS, follow_redirects=True) as cli:
                respuesta = await cli.get(url)
        except (httpx.TransportError, httpx.TimeoutException):
            if intento == _MAX_INTENTOS:
                break
            await asyncio.sleep(_BACKOFF_BASE_SEG * 2 ** (intento - 1))
            continue

        if respuesta.status_code == 404:
            return None
        if respuesta.status_code in (429, 403):
            raise AppError("Fuente no disponible", "ARCA_RATE_LIMITED", 503)
        if respuesta.status_code >= 500:
            if intento == _MAX_INTENTOS:
                break
            await asyncio.sleep(_BACKOFF_BASE_SEG * 2 ** (intento - 1))
            continue
        return respuesta

    logger.error("ARCA no disponible", extra={"url": url})
    raise AppError("ARCA no disponible", "ARCA_UNAVAILABLE", 503)


def construir_url(cuit: str, razon_social: str) -> str:
    """URL del detalle con slug de la razón social ('CRISTEM S A'→'cristem-s-a')."""
    ascii_ = unicodedata.normalize("NFKD", razon_social).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", ascii_))).strip("-")
    return f"{_BASE_URL}/detalle/{cuit}/{slug}.html"


async def obtener_constancia(url: str) -> dict | None:
    """Descarga y parsea el detalle; devuelve los campos crudos o None (404).

    Raises:
        AppError: 'ARCA_PERSONA_FISICA' (422) si el detalle es de una persona física;
            'ARCA_RATE_LIMITED'/'ARCA_UNAVAILABLE' (503) propagados de `_get`.
    """
    respuesta = await _get(url)
    if respuesta is None:
        return None
    raw = arca_parser.extraer_constancia(respuesta.text)
    if arca_parser.es_persona_fisica(raw):
        raise AppError(
            "El producto solo procesa personas jurídicas", "ARCA_PERSONA_FISICA", 422
        )
    return raw
