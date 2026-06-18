"""Tests de la maquinaria de jobs (services/job_service.py).

Se usa asyncio.run para no depender de plugins async de pytest. El pipeline de
fuentes es un stub: el resultado esperado es el placeholder.
"""

import asyncio
from uuid import uuid4

import pytest

from schemas.job import JobStatus
from services.job_service import crear_job, obtener_job, procesar_job
from utils.errors import AppError

CUIT_JURIDICA = "30716595540"
CUIT_FISICA = "20123456786"
RESULTADO_STUB = {"placeholder": "sin fuentes conectadas aún"}


def test_crear_job_juridica_queda_pending():
    job = asyncio.run(crear_job(CUIT_JURIDICA, "ACME SA"))
    assert job.status == JobStatus.PENDING
    assert job.cuit == CUIT_JURIDICA
    assert job.razon_social == "ACME SA"


def test_crear_job_fisica_no_permitida():
    with pytest.raises(AppError) as exc:
        asyncio.run(crear_job(CUIT_FISICA, None))
    assert exc.value.code == "PERSONA_FISICA_NOT_ALLOWED"
    assert exc.value.status_code == 422


def test_procesar_job_lleva_de_pending_a_done():
    async def flujo():
        job = await crear_job(CUIT_JURIDICA, None)
        assert job.status == JobStatus.PENDING
        return await procesar_job(job.id)

    procesado = asyncio.run(flujo())
    assert procesado.status == JobStatus.DONE
    assert procesado.resultado == RESULTADO_STUB
    assert procesado.error is None


def test_obtener_job_inexistente():
    with pytest.raises(AppError) as exc:
        asyncio.run(obtener_job(uuid4()))
    assert exc.value.code == "JOB_NOT_FOUND"
    assert exc.value.status_code == 404
