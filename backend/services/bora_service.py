"""Publicaciones de Boletines Oficiales (BORA) de una empresa, vía dateas.com.

Orquesta el flujo del Agente BORA: arma la URL, descarga la página y delega la
normalización en `services/bora_normalizer`. Todo el transporte/scraping vive en
`integrations/bora_client`; acá solo hay orquestación y traducción de "sin datos" a
errores de dominio. Patrón espejo de `arca_service`.
"""

from integrations import bora_client
from services import bora_normalizer
from utils.errors import AppError
from utils.logger import logger


async def obtener_datos_bora(cuit: str, razon_social: str) -> dict:
    """Descarga y normaliza las publicaciones del BORA (y datos de dateas) para un CUIT.

    Args:
        cuit: CUIT de 11 dígitos sin guiones, ya validado como persona jurídica.
        razon_social: Razón social de la empresa; insumo del slug de la URL de dateas.

    Returns:
        Dict normalizado con claves estables (ver `bora_normalizer.normalizar`).

    Raises:
        AppError: 'BORA_CUIT_NOT_FOUND' (404) si la página no existe (404 → raw None);
            'BORA_RATE_LIMITED'/'BORA_UNAVAILABLE' (503) propagados del cliente.
    """
    raw = await bora_client.obtener_datos(cuit, razon_social)
    if raw is None:
        raise AppError("CUIT no encontrado en BORA", "BORA_CUIT_NOT_FOUND", 404)
    datos = bora_normalizer.normalizar(raw)
    logger.info("Consulta BORA realizada", extra={"cuit": cuit})
    return datos
