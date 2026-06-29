"""Lógica de negocio de los jobs de consulta de CUIT.

Orquesta validación, creación y procesamiento. El pipeline real consulta el BCRA
(con caché) y redacta el informe con el analista IA; las fuentes externas se
consumen vía sus services (bcra_service, cache_service, report_service).
"""

from uuid import UUID

from repositories.job_repo import InMemoryJobRepository, JobRepository
from schemas.job import Job, JobStatus
from services import arca_service, bcra_service, cache_service, report_arca, report_service
from services.cuit_service import validar_cuit_juridica
from utils.errors import AppError
from utils.logger import logger

# Identificadores de fuente para keys y TTL de caché (cache_service).
_FUENTE_BCRA = "bcra"
_FUENTE_ARCA = "arca"

# Repositorio activo. Temporalmente en memoria; al conectar Supabase se reemplaza
# por SupabaseJobRepository (misma interfaz JobRepository).
job_repo: JobRepository = InMemoryJobRepository()


async def crear_job(cuit: str, razon_social: str | None) -> Job:
    """Valida el CUIT y crea un job en estado PENDING.

    Args:
        cuit: CUIT a consultar; debe corresponder a una persona jurídica.
        razon_social: Razón social opcional informada por el cliente.

    Returns:
        El job recién creado, en estado PENDING.

    Raises:
        AppError: codes 'INVALID_CUIT' / 'UNKNOWN_CUIT_PREFIX' /
            'PERSONA_FISICA_NOT_ALLOWED' según la validación del CUIT.
    """
    cuit_limpio = validar_cuit_juridica(cuit)
    job = await job_repo.create(cuit_limpio, razon_social)
    logger.info("Job creado", extra={"job_id": str(job.id)})
    return job


async def _ejecutar_pipeline(job: Job) -> dict:
    """Ejecuta el pipeline real de un job: BCRA (con caché) + informe IA.

    El CUIT ya viene validado como jurídica desde `crear_job`. Primero resuelve los
    datos del BCRA por caché: si hay HIT no golpea la fuente; si hay MISS consulta
    `bcra_service` y cachea el resultado normalizado antes de redactar. Cachear antes
    del informe es deliberado: si el redactor falla, un reintento no vuelve al BCRA.

    Args:
        job: Job en proceso, con el CUIT ya validado como persona jurídica.

    Returns:
        Dict con 'cuit', 'denominacion', los bloques BCRA ('datos_bcra', 'informe_bcra',
        'fuente_cache_bcra') y ARCA ('datos_arca', 'informe_arca', 'fuente_cache_arca',
        'arca_error'). ARCA es complementario: degrada a None sin tumbar el job.

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
        await cache_service.guardar_en_cache(
            _FUENTE_BCRA, cuit, datos, cache_service.TTL_BCRA
        )
    informe = await report_service.generar_informe(datos)
    logger.info("Informe BCRA generado", extra={"cuit": cuit})
    # Bloque ARCA — complementario e independiente: si falla (incl. sin razón social),
    # degrada a None con el error anotado sin tumbar el job; el informe BCRA se conserva.
    arca = {"datos_arca": None, "informe_arca": None, "fuente_cache_arca": False, "arca_error": None}
    try:
        if not (job.razon_social or "").strip():
            raise AppError("Razón social requerida para consulta ARCA", "ARCA_NO_RAZON_SOCIAL", 422)
        cacheado = await cache_service.obtener_cacheado(_FUENTE_ARCA, cuit)
        arca["fuente_cache_arca"] = cacheado is not None
        datos_arca = cacheado
        if datos_arca is None:
            datos_arca = await arca_service.obtener_datos_arca(cuit, job.razon_social)
            await cache_service.guardar_en_cache(
                _FUENTE_ARCA, cuit, datos_arca, cache_service.TTL_ARCA
            )
        arca["datos_arca"] = datos_arca
        arca["informe_arca"] = await report_arca.generar_informe_arca(datos_arca)
    except AppError as exc:
        logger.warning("ARCA degradado", extra={"cuit": cuit, "code": exc.code})
        arca["arca_error"] = {"message": exc.message, "code": exc.code}
    return {
        "cuit": cuit,
        "denominacion": datos.get("denominacion"),
        "datos_bcra": datos,
        "informe_bcra": informe,
        "fuente_cache_bcra": fuente_cache,
        **arca,
    }


async def procesar_job(job_id: UUID) -> Job:
    """Procesa un job: PROCESSING -> DONE (resultado) o ERROR (detalle del fallo).

    Args:
        job_id: Identificador del job a procesar.

    Returns:
        El job en su estado final (DONE o ERROR).

    Raises:
        AppError: code 'JOB_NOT_FOUND' (404) si el job no existe.
    """
    job = await obtener_job(job_id)
    await job_repo.update_status(job_id, JobStatus.PROCESSING)
    try:
        resultado = await _ejecutar_pipeline(job)
    except Exception as exc:
        code = exc.code if isinstance(exc, AppError) else "PIPELINE_ERROR"
        error = {"message": getattr(exc, "message", str(exc)), "code": code}
        actualizado = await job_repo.update_status(job_id, JobStatus.ERROR, error=error)
        logger.error("Job con error", extra={"job_id": str(job_id), "code": code})
        return actualizado
    actualizado = await job_repo.update_status(job_id, JobStatus.DONE, resultado=resultado)
    logger.info("Job finalizado", extra={"job_id": str(job_id)})
    return actualizado


async def obtener_job(job_id: UUID) -> Job:
    """Devuelve un job por su identificador.

    Args:
        job_id: Identificador del job.

    Returns:
        El job solicitado.

    Raises:
        AppError: code 'JOB_NOT_FOUND' (404) si el job no existe.
    """
    job = await job_repo.find_by_id(job_id)
    if job is None:
        raise AppError("Job no encontrado", "JOB_NOT_FOUND", 404)
    return job
