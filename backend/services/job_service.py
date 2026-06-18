"""Lógica de negocio de los jobs de consulta de CUIT.

Orquesta validación, creación y procesamiento. El pipeline de fuentes externas
(BCRA, ARCA, ...) todavía no está conectado: hoy devuelve un resultado stub.
"""

from uuid import UUID

from repositories.job_repo import InMemoryJobRepository, JobRepository
from schemas.job import Job, JobStatus
from services.cuit_service import validar_cuit_juridica
from utils.errors import AppError
from utils.logger import logger

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
    """Ejecuta el pipeline de fuentes de datos para un job.

    STUB temporal: todavía no hay fuentes conectadas. Aquí se enchufarán las
    fuentes reales (BCRA, ARCA, ...) usando job.cuit, combinando sus resultados.

    Args:
        job: Job en proceso, con el CUIT ya validado.

    Returns:
        El resultado combinado de las fuentes. Hoy, un placeholder.
    """
    # TODO: enchufar fuentes reales acá (BCRA, ARCA, ...) a partir de job.cuit.
    return {"placeholder": "sin fuentes conectadas aún"}


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
