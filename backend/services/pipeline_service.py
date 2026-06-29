"""Pipeline de enriquecimiento de un job: orquesta los agentes de fuentes externas.

Extraído de `job_service` (que quedaba en su límite de 150 líneas al sumar fuentes). El
BCRA es el núcleo: si cae, tumba el job. ARCA y BORA son complementarios e independientes:
cada uno resuelve por caché propia y, si falla (incl. falta de razón social), degrada a None
con su `*_error` anotado sin tumbar el job. Cada agente genera su informe por separado; el
unificador los cruza más adelante (Sesión 9).
"""

from schemas.job import Job
from services import (
    arca_service,
    bcra_service,
    bora_service,
    cache_service,
    report_arca,
    report_bora,
    report_service,
)
from utils.errors import AppError
from utils.logger import logger

_FUENTE_BCRA = "bcra"


async def _resolver_complementaria(fuente, cuit, razon_social, obtener, generar_informe, ttl):
    """Resuelve una fuente complementaria (ARCA/BORA) por caché + informe; degrada sin tumbar.

    Exige razón social (la URL de la fuente la necesita): si falta, degrada con
    `{FUENTE}_NO_RAZON_SOCIAL` sin consultar la fuente. Cualquier AppError (fuente caída,
    sin datos, informe inválido) también degrada. Cachea el dato normalizado antes de
    redactar, para que un reintento no vuelva a la fuente si cae el informe.

    Returns:
        Dict con 'datos', 'informe', 'fuente_cache' y 'error' ({message, code} o None).
    """
    res = {"datos": None, "informe": None, "fuente_cache": False, "error": None}
    try:
        if not (razon_social or "").strip():
            raise AppError(f"Razón social requerida para {fuente}", f"{fuente.upper()}_NO_RAZON_SOCIAL", 422)
        cacheado = await cache_service.obtener_cacheado(fuente, cuit)
        res["fuente_cache"] = cacheado is not None
        datos = cacheado
        if datos is None:
            datos = await obtener(cuit, razon_social)
            await cache_service.guardar_en_cache(fuente, cuit, datos, ttl)
        res["datos"] = datos
        res["informe"] = await generar_informe(datos)
    except AppError as exc:
        logger.warning(f"{fuente.upper()} degradado", extra={"cuit": cuit, "code": exc.code})
        res["error"] = {"message": exc.message, "code": exc.code}
    return res


async def ejecutar_pipeline(job: Job) -> dict:
    """Ejecuta el pipeline de un job: BCRA (núcleo, con caché) + ARCA y BORA (complementarios).

    El CUIT ya viene validado como jurídica. El BCRA se resuelve por caché y se cachea el
    normalizado ANTES de redactar (un reintento no vuelve a la fuente si cae el informe); su
    fallo propaga y tumba el job. ARCA y BORA degradan sin tumbar (ver `_resolver_complementaria`).

    Raises:
        AppError: 'BCRA_UNAVAILABLE'/'BCRA_INVALID_CUIT' si cae la deuda actual;
            'CLAUDE_UNAVAILABLE'/'REPORT_VALIDATION_FAILED' si falla el informe BCRA.
    """
    cuit = job.cuit
    datos = await cache_service.obtener_cacheado(_FUENTE_BCRA, cuit)
    fuente_cache = datos is not None
    if fuente_cache:
        logger.info("Cache hit BCRA", extra={"cuit": cuit})
    else:
        logger.info("Cache miss BCRA", extra={"cuit": cuit})
        datos = await bcra_service.obtener_situacion_crediticia(cuit)
        await cache_service.guardar_en_cache(_FUENTE_BCRA, cuit, datos, cache_service.TTL_BCRA)
    informe = await report_service.generar_informe(datos)
    logger.info("Informe BCRA generado", extra={"cuit": cuit})

    arca = await _resolver_complementaria(
        "arca", cuit, job.razon_social,
        arca_service.obtener_datos_arca, report_arca.generar_informe_arca, cache_service.TTL_ARCA,
    )
    bora = await _resolver_complementaria(
        "bora", cuit, job.razon_social,
        bora_service.obtener_datos_bora, report_bora.generar_informe_bora, cache_service.TTL_BORA,
    )
    return {
        "cuit": cuit,
        "denominacion": datos.get("denominacion"),
        "datos_bcra": datos,
        "informe_bcra": informe,
        "fuente_cache_bcra": fuente_cache,
        "datos_arca": arca["datos"],
        "informe_arca": arca["informe"],
        "fuente_cache_arca": arca["fuente_cache"],
        "arca_error": arca["error"],
        "datos_bora": bora["datos"],
        "informe_bora": bora["informe"],
        "fuente_cache_bora": bora["fuente_cache"],
        "bora_error": bora["error"],
    }
