"""Tests de la maquinaria de jobs (services/job_service.py).

Se usa asyncio.run para no depender de plugins async de pytest. El pipeline real
(BCRA + caché + informe IA) se prueba mockeando `bcra_service` y `report_service`
en el namespace de `job_service`: nunca se pega a una API real. La caché en memoria
se resetea antes de cada test para aislar HIT/MISS entre casos.
"""

import asyncio
from uuid import uuid4

import pytest

from repositories.cache_repo import InMemoryCacheRepository
from schemas.job import JobStatus
from services import cache_service, job_service
from services.job_service import crear_job, obtener_job, procesar_job
from utils.errors import AppError

CUIT_JURIDICA = "30716595540"
CUIT_FISICA = "20123456786"

DATOS_BCRA = {
    "denominacion": "ACME SA",
    "actual": {"situacion_maxima": 1, "entidades_activas": 2},
    "historico": {},
    "cheques": {},
}
INFORME = "La empresa registra situación 1 en todas las entidades activas."


@pytest.fixture(autouse=True)
def _reset_cache():
    """Resetea la caché en memoria antes de cada test para aislar HIT/MISS."""
    cache_service.cache_repo = InMemoryCacheRepository()
    yield


def _mock_bcra(monkeypatch, *, resultado=None, error=None):
    """Mockea bcra_service.obtener_situacion_crediticia y cuenta sus llamadas."""
    llamadas = {"n": 0}

    async def fake(cuit):
        llamadas["n"] += 1
        if error is not None:
            raise error
        return resultado

    monkeypatch.setattr(job_service.bcra_service, "obtener_situacion_crediticia", fake)
    return llamadas


def _mock_report(monkeypatch, *, resultado=None, error=None):
    """Mockea report_service.generar_informe y cuenta sus llamadas."""
    llamadas = {"n": 0}

    async def fake(datos):
        llamadas["n"] += 1
        if error is not None:
            raise error
        return resultado

    monkeypatch.setattr(job_service.report_service, "generar_informe", fake)
    return llamadas


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


def test_pipeline_cache_miss_consulta_bcra_y_genera_informe(monkeypatch):
    bcra = _mock_bcra(monkeypatch, resultado=DATOS_BCRA)
    report = _mock_report(monkeypatch, resultado=INFORME)

    async def flujo():
        job = await crear_job(CUIT_JURIDICA, None)
        procesado = await procesar_job(job.id)
        cacheado = await cache_service.obtener_cacheado("bcra", CUIT_JURIDICA)
        return procesado, cacheado

    procesado, cacheado = asyncio.run(flujo())
    assert bcra["n"] == 1  # MISS: se consultó el BCRA
    assert report["n"] == 1
    assert procesado.status == JobStatus.DONE
    assert procesado.error is None
    assert procesado.resultado["informe"] == INFORME
    assert procesado.resultado["fuente_cache"] is False
    assert procesado.resultado["denominacion"] == "ACME SA"
    assert procesado.resultado["datos_bcra"] == DATOS_BCRA
    assert cacheado == DATOS_BCRA  # quedó cacheado tras el MISS


def test_pipeline_cache_hit_no_consulta_bcra(monkeypatch):
    bcra = _mock_bcra(monkeypatch, error=AssertionError("no debe llamarse en HIT"))
    report = _mock_report(monkeypatch, resultado=INFORME)

    async def flujo():
        await cache_service.guardar_en_cache(
            "bcra", CUIT_JURIDICA, DATOS_BCRA, cache_service.TTL_BCRA
        )
        job = await crear_job(CUIT_JURIDICA, None)
        return await procesar_job(job.id)

    procesado = asyncio.run(flujo())
    assert bcra["n"] == 0  # HIT: NO se consultó el BCRA
    assert report["n"] == 1
    assert procesado.status == JobStatus.DONE
    assert procesado.resultado["fuente_cache"] is True
    assert procesado.resultado["datos_bcra"] == DATOS_BCRA


def test_pipeline_bcra_unavailable_deja_error_y_no_cachea(monkeypatch):
    bcra = _mock_bcra(
        monkeypatch, error=AppError("BCRA caído", "BCRA_UNAVAILABLE", 503)
    )
    report = _mock_report(monkeypatch, resultado=INFORME)

    async def flujo():
        job = await crear_job(CUIT_JURIDICA, None)
        procesado = await procesar_job(job.id)
        cacheado = await cache_service.obtener_cacheado("bcra", CUIT_JURIDICA)
        return procesado, cacheado

    procesado, cacheado = asyncio.run(flujo())
    assert procesado.status == JobStatus.ERROR
    assert procesado.error["code"] == "BCRA_UNAVAILABLE"
    assert report["n"] == 0  # nunca se llegó al informe
    assert cacheado is None  # no se cacheó nada


def test_pipeline_informe_falla_pero_bcra_queda_cacheado(monkeypatch):
    bcra = _mock_bcra(monkeypatch, resultado=DATOS_BCRA)
    report = _mock_report(
        monkeypatch, error=AppError("Claude caído", "CLAUDE_UNAVAILABLE", 503)
    )

    async def flujo():
        job = await crear_job(CUIT_JURIDICA, None)
        primero = await procesar_job(job.id)
        # Segundo intento: el BCRA ya quedó cacheado, no se vuelve a consultar.
        job2 = await crear_job(CUIT_JURIDICA, None)
        segundo = await procesar_job(job2.id)
        return primero, segundo

    primero, segundo = asyncio.run(flujo())
    assert primero.status == JobStatus.ERROR
    assert primero.error["code"] == "CLAUDE_UNAVAILABLE"
    assert segundo.status == JobStatus.ERROR  # sigue fallando el informe
    assert bcra["n"] == 1  # el BCRA se consultó UNA sola vez (HIT en el reintento)


def test_procesar_job_inexistente():
    with pytest.raises(AppError) as exc:
        asyncio.run(procesar_job(uuid4()))
    assert exc.value.code == "JOB_NOT_FOUND"


def test_obtener_job_inexistente():
    with pytest.raises(AppError) as exc:
        asyncio.run(obtener_job(uuid4()))
    assert exc.value.code == "JOB_NOT_FOUND"
    assert exc.value.status_code == 404
