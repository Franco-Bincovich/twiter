"""Endpoints de consultas de CUIT (jobs async). Sin lógica de negocio."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, status

from controllers.job_controller import crear_consulta, obtener_consulta
from schemas.job import JobCreateRequest, JobResponse

router = APIRouter(prefix="/consultas", tags=["consultas"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
async def crear_consulta_endpoint(
    payload: JobCreateRequest, background_tasks: BackgroundTasks
) -> JobResponse:
    return await crear_consulta(payload, background_tasks)


@router.get("/{job_id}", response_model=JobResponse)
async def obtener_consulta_endpoint(job_id: UUID) -> JobResponse:
    return await obtener_consulta(job_id)
