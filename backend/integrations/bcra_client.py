"""Cliente HTTP de la Central de Deudores del BCRA (wrapper de transporte).

Aísla TODA llamada a la API del BCRA: el resto del backend nunca habla HTTP con el
BCRA directamente, solo este módulo (SEGURIDAD-PENTEST.md 6.2). Sin lógica de
negocio: solo hace el request, reintenta ante cortes y traduce el resultado a
`dict results | None`. La normalización vive en `services/bcra_service`.

La API es pública y sin autenticación. Corta conexiones de forma intermitente
("server closed abruptly"), por eso cada request se reintenta con backoff
exponencial en vez de una sola llamada. Devuelve el body como JSON aunque el
Content-Type sea text/plain, por eso el parseo cae a `json.loads(text)`.
"""

import asyncio
import json

import httpx

from utils.errors import AppError
from utils.logger import logger

# Endpoint público fijo del BCRA (Central de Deudores). No requiere API key.
_BASE_URL = "https://api.bcra.gob.ar"
_PREFIJO = "/centraldedeudores/v1.0/Deudas"

_TIMEOUT_SEG = 10.0          # timeout explícito por intento
_MAX_INTENTOS = 3            # la API corta conexiones: reintentar, no fallar a la primera
_BACKOFF_BASE_SEG = 0.5      # espera = base * 2**(intento-1): 0.5s, 1s, 2s

# El BCRA responde un header `x-jws-signature` (firma de integridad del payload).
# No se valida por ahora; queda anotado para validación futura de la firma.


async def _get_results(path: str) -> dict | None:
    """Hace GET a un endpoint del BCRA con reintentos y devuelve su `results`.

    Reintenta con backoff exponencial ante corte de conexión, timeout o 5xx (la API
    cierra conexiones de forma intermitente). El 404 no se reintenta: es "sin datos",
    un resultado válido. El 400 tampoco: es un CUIT inválido para el BCRA.

    Args:
        path: Ruta absoluta del endpoint (sin el host), ya con el CUIT embebido.

    Returns:
        El objeto `results` del body (dict) en un 200, o None si el BCRA respondió
        404 (sin datos para ese CUIT).

    Raises:
        AppError: 'BCRA_INVALID_CUIT' (400) si el BCRA rechaza el CUIT;
            'BCRA_UNAVAILABLE' (503) si tras agotar los reintentos sigue sin
            responder (corte de conexión, timeout o 5xx).
    """
    url = f"{_BASE_URL}{path}"
    for intento in range(1, _MAX_INTENTOS + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SEG) as cliente:
                respuesta = await cliente.get(url)
        except (httpx.TransportError, httpx.TimeoutException):
            # Corte de conexión o timeout: reintentar salvo que sea el último intento.
            if intento == _MAX_INTENTOS:
                break
            await asyncio.sleep(_BACKOFF_BASE_SEG * 2 ** (intento - 1))
            continue

        if respuesta.status_code == 404:
            return None  # sin datos para ese CUIT: resultado válido, no error
        if respuesta.status_code == 400:
            raise AppError("CUIT inválido para BCRA", "BCRA_INVALID_CUIT", 400)
        if respuesta.status_code >= 500:
            # Error del servidor: reintentar salvo que sea el último intento.
            if intento == _MAX_INTENTOS:
                break
            await asyncio.sleep(_BACKOFF_BASE_SEG * 2 ** (intento - 1))
            continue

        body = _parsear_body(respuesta)
        return body.get("results")

    logger.error("BCRA no disponible", extra={"path": path})
    raise AppError("Servicio BCRA no disponible", "BCRA_UNAVAILABLE", 503)


def _parsear_body(respuesta: httpx.Response) -> dict:
    """Parsea el body como JSON aunque el Content-Type sea text/plain."""
    try:
        return respuesta.json()
    except (json.JSONDecodeError, ValueError):
        # El BCRA a veces marca el JSON como text/plain: parsear el texto a mano.
        return json.loads(respuesta.text)


async def consultar_deudas(cuit: str) -> dict | None:
    """Consulta la situación de deuda ACTUAL del CUIT en el BCRA.

    Args:
        cuit: CUIT de 11 dígitos sin guiones (ya validado por `cuit_service`).

    Returns:
        El `results` del endpoint (dict) o None si el BCRA no tiene datos (404).

    Raises:
        AppError: 'BCRA_INVALID_CUIT' (400) o 'BCRA_UNAVAILABLE' (503).
    """
    return await _get_results(f"{_PREFIJO}/{cuit}")


async def consultar_historicas(cuit: str) -> dict | None:
    """Consulta el histórico de deuda (24 meses) del CUIT en el BCRA.

    Args:
        cuit: CUIT de 11 dígitos sin guiones (ya validado por `cuit_service`).

    Returns:
        El `results` del endpoint (dict) o None si el BCRA no tiene datos (404).

    Raises:
        AppError: 'BCRA_INVALID_CUIT' (400) o 'BCRA_UNAVAILABLE' (503).
    """
    return await _get_results(f"{_PREFIJO}/Historicas/{cuit}")


async def consultar_cheques(cuit: str) -> dict | None:
    """Consulta los cheques rechazados del CUIT en el BCRA.

    Args:
        cuit: CUIT de 11 dígitos sin guiones (ya validado por `cuit_service`).

    Returns:
        El `results` del endpoint (dict) o None si el BCRA no tiene datos (404).

    Raises:
        AppError: 'BCRA_INVALID_CUIT' (400) o 'BCRA_UNAVAILABLE' (503).
    """
    return await _get_results(f"{_PREFIJO}/ChequesRechazados/{cuit}")
