"""Tests de la maquinaria de jobs y del pipeline de enriquecimiento.

Se usa asyncio.run para no depender de plugins async de pytest. El pipeline real
(BCRA núcleo + ARCA y BORA complementarios) vive en `pipeline_service`; se mockean sus
services e informes en ese namespace, nunca se pega a una API real. La caché en memoria se
resetea antes de cada test para aislar HIT/MISS entre casos.
"""

import asyncio
from uuid import uuid4

import pytest

from repositories.cache_repo import InMemoryCacheRepository
from schemas.job import JobStatus
from services import cache_service, job_service, pipeline_service
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

DATOS_ARCA = {"razon_social": "Acme Sa", "estado_inscripcion": "activo", "nivel_alerta": "bajo"}
INFORME_ARCA = "La empresa figura con inscripción activa en ARCA."

DATOS_BORA = {"razon_social": "Acme Sa", "nivel_alerta": "bajo", "publicaciones": []}
INFORME_BORA = "La empresa no registra publicaciones críticas en el BORA."


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

    monkeypatch.setattr(pipeline_service.bcra_service, "obtener_situacion_crediticia", fake)
    return llamadas


def _mock_report(monkeypatch, *, resultado=None, error=None):
    """Mockea report_service.generar_informe (BCRA) y cuenta sus llamadas."""
    llamadas = {"n": 0}

    async def fake(datos):
        llamadas["n"] += 1
        if error is not None:
            raise error
        return resultado

    monkeypatch.setattr(pipeline_service.report_service, "generar_informe", fake)
    return llamadas


def _mock_complementaria(monkeypatch, modulo, attr, *, resultado=None, error=None):
    """Mockea un service/redactor complementario y cuenta sus llamadas.

    Sirve para ARCA/BORA: los services reciben (cuit, razon_social) y los redactores (datos);
    el fake acepta cualquier firma con *args.
    """
    llamadas = {"n": 0}

    async def fake(*args):
        llamadas["n"] += 1
        if error is not None:
            raise error
        return resultado

    monkeypatch.setattr(getattr(pipeline_service, modulo), attr, fake)
    return llamadas


def _mock_arca(monkeypatch, *, resultado=None, error=None):
    """Mockea arca_service.obtener_datos_arca."""
    return _mock_complementaria(monkeypatch, "arca_service", "obtener_datos_arca", resultado=resultado, error=error)


def _mock_report_arca(monkeypatch, *, resultado=None, error=None):
    """Mockea report_arca.generar_informe_arca."""
    return _mock_complementaria(monkeypatch, "report_arca", "generar_informe_arca", resultado=resultado, error=error)


def _mock_bora(monkeypatch, *, resultado=None, error=None):
    """Mockea bora_service.obtener_datos_bora."""
    return _mock_complementaria(monkeypatch, "bora_service", "obtener_datos_bora", resultado=resultado, error=error)


def _mock_report_bora(monkeypatch, *, resultado=None, error=None):
    """Mockea report_bora.generar_informe_bora."""
    return _mock_complementaria(monkeypatch, "report_bora", "generar_informe_bora", resultado=resultado, error=error)


def _mock_complementarias_ok(monkeypatch):
    """Mockea ARCA y BORA con resultados válidos (para tests centrados en el BCRA)."""
    _mock_arca(monkeypatch, resultado=DATOS_ARCA)
    _mock_report_arca(monkeypatch, resultado=INFORME_ARCA)
    _mock_bora(monkeypatch, resultado=DATOS_BORA)
    _mock_report_bora(monkeypatch, resultado=INFORME_BORA)


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
    arca = _mock_arca(monkeypatch, resultado=DATOS_ARCA)
    report_arca = _mock_report_arca(monkeypatch, resultado=INFORME_ARCA)
    bora = _mock_bora(monkeypatch, resultado=DATOS_BORA)
    report_bora = _mock_report_bora(monkeypatch, resultado=INFORME_BORA)

    async def flujo():
        # razón social presente: ARCA y BORA pueden construir la URL y proceder.
        job = await crear_job(CUIT_JURIDICA, "ACME SA")
        procesado = await procesar_job(job.id)
        cacheado = await cache_service.obtener_cacheado("bcra", CUIT_JURIDICA)
        return procesado, cacheado

    procesado, cacheado = asyncio.run(flujo())
    assert bcra["n"] == 1  # MISS: se consultó el BCRA
    assert report["n"] == 1
    assert arca["n"] == 1 and report_arca["n"] == 1  # MISS: se consultó ARCA
    assert bora["n"] == 1 and report_bora["n"] == 1  # MISS: se consultó BORA
    assert procesado.status == JobStatus.DONE
    assert procesado.error is None
    assert procesado.resultado["informe_bcra"] == INFORME
    assert procesado.resultado["fuente_cache_bcra"] is False
    assert procesado.resultado["denominacion"] == "ACME SA"
    assert procesado.resultado["datos_bcra"] == DATOS_BCRA
    # Bloques ARCA y BORA (independientes del BCRA), resueltos en el mismo job.
    assert procesado.resultado["informe_arca"] == INFORME_ARCA
    assert procesado.resultado["datos_arca"] == DATOS_ARCA
    assert procesado.resultado["arca_error"] is None
    assert procesado.resultado["informe_bora"] == INFORME_BORA
    assert procesado.resultado["fuente_cache_bora"] is False
    assert procesado.resultado["datos_bora"] == DATOS_BORA
    assert procesado.resultado["bora_error"] is None
    assert cacheado == DATOS_BCRA  # quedó cacheado tras el MISS


def test_pipeline_cache_hit_no_consulta_bcra(monkeypatch):
    bcra = _mock_bcra(monkeypatch, error=AssertionError("no debe llamarse en HIT"))
    report = _mock_report(monkeypatch, resultado=INFORME)
    _mock_complementarias_ok(monkeypatch)

    async def flujo():
        await cache_service.guardar_en_cache(
            "bcra", CUIT_JURIDICA, DATOS_BCRA, cache_service.TTL_BCRA
        )
        job = await crear_job(CUIT_JURIDICA, "ACME SA")
        return await procesar_job(job.id)

    procesado = asyncio.run(flujo())
    assert bcra["n"] == 0  # HIT: NO se consultó el BCRA
    assert report["n"] == 1
    assert procesado.status == JobStatus.DONE
    assert procesado.resultado["fuente_cache_bcra"] is True
    assert procesado.resultado["datos_bcra"] == DATOS_BCRA


def test_pipeline_arca_degrada_sin_tumbar_el_job(monkeypatch):
    # ARCA caído NO debe tumbar el job: el informe BCRA se conserva y ARCA queda en
    # None con el error anotado (informes independientes). BORA resuelve aparte.
    _mock_bcra(monkeypatch, resultado=DATOS_BCRA)
    _mock_report(monkeypatch, resultado=INFORME)
    arca = _mock_arca(
        monkeypatch, error=AppError("CUIT no encontrado en ARCA", "ARCA_CUIT_NOT_FOUND", 404)
    )
    report_arca = _mock_report_arca(monkeypatch, resultado=INFORME_ARCA)
    _mock_bora(monkeypatch, resultado=DATOS_BORA)
    _mock_report_bora(monkeypatch, resultado=INFORME_BORA)

    async def flujo():
        # razón social presente: ARCA llega a la fuente, que falla y degrada.
        job = await crear_job(CUIT_JURIDICA, "ACME SA")
        return await procesar_job(job.id)

    procesado = asyncio.run(flujo())
    assert arca["n"] == 1
    assert report_arca["n"] == 0  # nunca se llegó al informe ARCA
    assert procesado.status == JobStatus.DONE  # el job NO se cae por ARCA
    assert procesado.resultado["informe_bcra"] == INFORME  # BCRA conservado
    assert procesado.resultado["datos_arca"] is None
    assert procesado.resultado["informe_arca"] is None
    assert procesado.resultado["arca_error"]["code"] == "ARCA_CUIT_NOT_FOUND"
    # BORA es independiente: resolvió bien aunque ARCA cayó.
    assert procesado.resultado["informe_bora"] == INFORME_BORA
    assert procesado.resultado["bora_error"] is None


def test_pipeline_arca_sin_razon_social_degrada(monkeypatch):
    # Sin razón social no se puede construir la URL de ARCA/BORA: ambas degradan con
    # *_NO_RAZON_SOCIAL sin tumbar el job y sin llegar a consultar la fuente.
    _mock_bcra(monkeypatch, resultado=DATOS_BCRA)
    _mock_report(monkeypatch, resultado=INFORME)
    arca = _mock_arca(monkeypatch, resultado=DATOS_ARCA)
    report_arca = _mock_report_arca(monkeypatch, resultado=INFORME_ARCA)
    bora = _mock_bora(monkeypatch, resultado=DATOS_BORA)

    async def flujo():
        job = await crear_job(CUIT_JURIDICA, None)  # sin razón social
        return await procesar_job(job.id)

    procesado = asyncio.run(flujo())
    assert arca["n"] == 0  # NUNCA se consultó la fuente ARCA
    assert report_arca["n"] == 0
    assert bora["n"] == 0  # NUNCA se consultó la fuente BORA
    assert procesado.status == JobStatus.DONE  # el job NO se cae
    assert procesado.resultado["informe_bcra"] == INFORME  # BCRA conservado
    assert procesado.resultado["datos_arca"] is None
    assert procesado.resultado["arca_error"]["code"] == "ARCA_NO_RAZON_SOCIAL"


def test_pipeline_bora_sin_razon_social_degrada(monkeypatch):
    # Espejo del caso ARCA, enfocado en BORA: sin razón social degrada con
    # BORA_NO_RAZON_SOCIAL sin consultar dateas y sin tumbar el job.
    _mock_bcra(monkeypatch, resultado=DATOS_BCRA)
    _mock_report(monkeypatch, resultado=INFORME)
    _mock_arca(monkeypatch, resultado=DATOS_ARCA)
    _mock_report_arca(monkeypatch, resultado=INFORME_ARCA)
    bora = _mock_bora(monkeypatch, resultado=DATOS_BORA)
    report_bora = _mock_report_bora(monkeypatch, resultado=INFORME_BORA)

    async def flujo():
        job = await crear_job(CUIT_JURIDICA, None)  # sin razón social
        return await procesar_job(job.id)

    procesado = asyncio.run(flujo())
    assert bora["n"] == 0  # NUNCA se consultó la fuente BORA
    assert report_bora["n"] == 0  # nunca se llegó al informe BORA
    assert procesado.status == JobStatus.DONE  # el job NO se cae
    assert procesado.resultado["informe_bcra"] == INFORME  # BCRA conservado
    assert procesado.resultado["datos_bora"] is None
    assert procesado.resultado["informe_bora"] is None
    assert procesado.resultado["bora_error"]["code"] == "BORA_NO_RAZON_SOCIAL"


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
