"""Orquestación de las consultas de CUIT entre el router y el service."""

from uuid import UUID

from fastapi import BackgroundTasks

from schemas.job import JobCreateRequest, JobResponse
from services.job_service import crear_job, obtener_job, procesar_job


async def crear_consulta(
    payload: JobCreateRequest, background_tasks: BackgroundTasks
) -> JobResponse:
    """Crea un job y dispara su procesamiento en background.

    Args:
        payload: Datos de la consulta (cuit y razón social opcional).
        background_tasks: Cola de tareas en background de FastAPI.

    Returns:
        El job recién creado, en estado PENDING.
    """
    job = await crear_job(payload.cuit, payload.razon_social)
    background_tasks.add_task(procesar_job, job.id)
    return JobResponse.model_validate(job)


async def obtener_consulta(job_id: UUID) -> JobResponse:
    """Devuelve el estado actual de una consulta para polling.

    Args:
        job_id: Identificador del job.

    Returns:
        El job con su estado actual.
    """
    job = await obtener_job(job_id)
    return JobResponse.model_validate(job)
