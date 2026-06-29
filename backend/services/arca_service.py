"""Datos de inscripción de una empresa en ARCA (ex AFIP), vía cuitonline.com.

Orquesta el flujo del Agente ARCA: busca el CUIT, descarga la constancia y delega la
normalización en `services/arca_normalizer`. Todo el transporte/scraping vive en
`integrations/arca_client`; acá solo hay orquestación y traducción de "sin datos" a
errores de dominio. Patrón espejo de `bcra_service`.
"""

from integrations import arca_client
from services import arca_normalizer
from utils.errors import AppError
from utils.logger import logger


async def obtener_datos_arca(cuit: str, razon_social: str) -> dict:
    """Arma la URL del detalle, descarga la constancia y normaliza los datos de ARCA.

    La URL se construye directamente desde el CUIT y la razón social (no hay búsqueda
    previa en cuitonline): `construir_url` genera el slug url-friendly.

    Args:
        cuit: CUIT de 11 dígitos sin guiones, ya validado como persona jurídica.
        razon_social: Razón social de la empresa; insumo del slug de la URL del detalle.

    Returns:
        Dict normalizado con claves estables (ver `arca_normalizer.normalizar`).

    Raises:
        AppError: 'ARCA_CUIT_NOT_FOUND' (404) si el detalle no existe (404 → raw None);
            'ARCA_RATE_LIMITED'/'ARCA_UNAVAILABLE' (503) o 'ARCA_PERSONA_FISICA' (422)
            propagados del cliente.
    """
    url = arca_client.construir_url(cuit, razon_social)
    raw = await arca_client.obtener_constancia(url)
    if raw is None:
        raise AppError("CUIT no encontrado en ARCA", "ARCA_CUIT_NOT_FOUND", 404)
    datos = arca_normalizer.normalizar(raw)
    logger.info("Consulta ARCA realizada", extra={"cuit": cuit})
    return datos
