"""Tests del servicio BCRA (services/bcra_service.py).

NO se le pega a la API real del BCRA: se mockea `bcra_client` (sus tres funciones
async) con monkeypatch. Se usa asyncio.run para no depender de plugins async de
pytest, igual que el resto de la suite. Se verifica la normalización confirmada con
datos reales: deudas ×1000, cheques sin multiplicar, peor situación, flags y la
tolerancia a fallos (histórico/cheques se degradan; la deuda actual propaga).
"""

import asyncio

import pytest

from services import bcra_service
from utils.errors import AppError

CUIT = "30712345670"


def _entidad(situacion, monto, **flags):
    """Arma una entidad cruda del BCRA con valores por defecto y flags opcionales."""
    base = {
        "entidad": flags.pop("entidad", "BANCO X"),
        "situacion": situacion,
        "monto": monto,
        "diasAtrasoPago": 0,
        "fechaSit1": None,
        "refinanciaciones": False,
        "recategorizacionOblig": False,
        "situacionJuridica": False,
        "irrecDisposicionTecnica": False,
        "enRevision": False,
        "procesoJud": False,
    }
    base.update(flags)
    return base


def _deudas(denominacion, periodo, entidades):
    """Arma el `results` del endpoint de deudas/históricas."""
    return {
        "identificacion": CUIT,
        "denominacion": denominacion,
        "periodos": [{"periodo": periodo, "entidades": entidades}],
    }


def _mockear(monkeypatch, *, deudas, historicas, cheques):
    """Reemplaza las tres funciones del cliente BCRA por valores/excepciones fijos."""
    async def _resolver(valor):
        if isinstance(valor, BaseException):
            raise valor
        return valor

    monkeypatch.setattr(bcra_service.bcra_client, "consultar_deudas", lambda c: _resolver(deudas))
    monkeypatch.setattr(bcra_service.bcra_client, "consultar_historicas", lambda c: _resolver(historicas))
    monkeypatch.setattr(bcra_service.bcra_client, "consultar_cheques", lambda c: _resolver(cheques))


def test_empresa_sana(monkeypatch):
    # Situación 1, sin flags, sin cheques (404 → None en cheques).
    deudas = _deudas("EMPRESA SANA SA", "202405", [_entidad(1, 100.0)])
    _mockear(monkeypatch, deudas=deudas, historicas=deudas, cheques=None)

    res = asyncio.run(bcra_service.obtener_situacion_crediticia(CUIT))

    assert res["denominacion"] == "EMPRESA SANA SA"
    assert res["actual"]["situacion_maxima"] == 1
    assert res["actual"]["entidades_activas"] == 1
    assert res["actual"]["deuda_total"] == 100_000.0  # 100 miles → pesos reales
    assert all(v == 0 for v in res["actual"]["flags_activos"].values())
    assert res["cheques"]["tiene_cheques"] is False
    assert res["cheques"]["total_cheques"] == 0


def test_empresa_default_flags_y_montos(monkeypatch):
    # Situación 5, situacionJuridica en 2 entidades, montos de deuda en miles,
    # cheques con varios registros en pesos reales.
    entidades = [
        _entidad(5, 1500.0, entidad="BANCO A", situacionJuridica=True, procesoJud=True),
        _entidad(5, 2500.0, entidad="BANCO B", situacionJuridica=True),
        _entidad(3, 800.0, entidad="BANCO C"),
    ]
    deudas = _deudas("EMPRESA DEFAULT SA", "202405", entidades)
    cheques = {
        "identificacion": CUIT,
        "denominacion": "EMPRESA DEFAULT SA",
        "causales": [
            {
                "causal": "SIN FONDOS",
                "entidades": [
                    {
                        "entidad": 11,
                        "detalle": [
                            {"nroCheque": 1, "monto": 30979876.86, "fechaPago": None},
                            {"nroCheque": 2, "monto": 500000.50, "fechaPago": "2024-05-01"},
                        ],
                    }
                ],
            },
            {
                "causal": "DEFECTOS FORMALES",
                "entidades": [{"entidad": 12, "detalle": [{"nroCheque": 3, "monto": 1000.0, "fechaPago": None}]}],
            },
        ],
    }
    _mockear(monkeypatch, deudas=deudas, historicas=deudas, cheques=cheques)

    res = asyncio.run(bcra_service.obtener_situacion_crediticia(CUIT))

    # situacion_maxima = el peor (más alto) entre 5, 5, 3.
    assert res["actual"]["situacion_maxima"] == 5
    assert res["actual"]["flags_activos"]["situacion_juridica"] == 2
    assert res["actual"]["flags_activos"]["proceso_judicial"] == 1
    # Deudas ×1000: (1500 + 2500 + 800) * 1000.
    assert res["actual"]["deuda_total"] == 4_800_000.0
    # Cheques SIN ×1000: suma de los montos reales tal cual.
    assert res["cheques"]["tiene_cheques"] is True
    assert res["cheques"]["total_cheques"] == 3
    assert res["cheques"]["total_pagados"] == 1
    assert res["cheques"]["monto_total"] == pytest.approx(30979876.86 + 500000.50 + 1000.0)
    assert res["cheques"]["mayor_cheque"] == pytest.approx(30979876.86)
    assert res["cheques"]["por_causal"] == {"SIN FONDOS": 2, "DEFECTOS FORMALES": 1}


def test_404_en_los_tres_endpoints(monkeypatch):
    # Sin datos en ninguno: todas las secciones con sus defaults vacíos, sin reventar.
    _mockear(monkeypatch, deudas=None, historicas=None, cheques=None)

    res = asyncio.run(bcra_service.obtener_situacion_crediticia(CUIT))

    assert res["denominacion"] is None
    assert res["actual"]["situacion_maxima"] is None
    assert res["actual"]["entidades_activas"] == 0
    assert res["actual"]["deuda_total"] == 0.0
    assert res["actual"]["flags_activos"] == {
        "situacion_juridica": 0, "proceso_judicial": 0, "recategorizacion": 0,
        "refinanciaciones": 0, "irrecuperable": 0,
    }
    assert res["historico"] == {"periodos_analizados": 0, "desvios": []}
    assert res["cheques"]["tiene_cheques"] is False
    assert res["cheques"]["monto_total"] == 0.0


def test_falla_deuda_actual_propaga(monkeypatch):
    # Si cae el endpoint núcleo (deuda actual), el error se propaga.
    error = AppError("Servicio BCRA no disponible", "BCRA_UNAVAILABLE", 503)
    _mockear(monkeypatch, deudas=error, historicas=None, cheques=None)

    with pytest.raises(AppError) as exc:
        asyncio.run(bcra_service.obtener_situacion_crediticia(CUIT))
    assert exc.value.code == "BCRA_UNAVAILABLE"
    assert exc.value.status_code == 503


def test_falla_solo_cheques_degrada_sin_tumbar(monkeypatch):
    # Si cae solo cheques (o histórico), su sección queda vacía pero el informe se arma.
    deudas = _deudas("EMPRESA SA", "202405", [_entidad(2, 300.0)])
    error = AppError("Servicio BCRA no disponible", "BCRA_UNAVAILABLE", 503)
    _mockear(monkeypatch, deudas=deudas, historicas=error, cheques=error)

    res = asyncio.run(bcra_service.obtener_situacion_crediticia(CUIT))

    assert res["actual"]["situacion_maxima"] == 2
    assert res["actual"]["deuda_total"] == 300_000.0
    # Secciones degradadas a vacío, sin excepción.
    assert res["historico"] == {"periodos_analizados": 0, "desvios": []}
    assert res["cheques"]["tiene_cheques"] is False


def test_situacion_maxima_toma_el_peor_del_periodo_reciente(monkeypatch):
    # Varias entidades en el periodo más reciente: gana el peor número (más alto).
    reciente = {
        "periodo": "202405",
        "entidades": [_entidad(1, 10.0), _entidad(4, 20.0), _entidad(2, 30.0)],
    }
    viejo = {"periodo": "202401", "entidades": [_entidad(5, 99.0)]}
    deudas = {
        "identificacion": CUIT,
        "denominacion": "EMPRESA SA",
        # Orden invertido a propósito: el servicio debe elegir el periodo mayor.
        "periodos": [viejo, reciente],
    }
    historicas = {
        "identificacion": CUIT,
        "denominacion": "EMPRESA SA",
        "periodos": [
            # situación 1 (normal) y 0 (sin deuda informada): ninguna es desvío.
            {"periodo": "202404", "entidades": [_entidad(1, 5.0), _entidad(0, 0.0, entidad="BANCO 0")]},
            # situación 3 (riesgo): sí es desvío.
            {"periodo": "202403", "entidades": [_entidad(3, 5.0, entidad="BANCO Z")]},
        ],
    }
    _mockear(monkeypatch, deudas=deudas, historicas=historicas, cheques=None)

    res = asyncio.run(bcra_service.obtener_situacion_crediticia(CUIT))

    # Del periodo 202405 (el más reciente), peor situación = 4, NO el 5 del viejo.
    assert res["actual"]["periodo"] == "202405"
    assert res["actual"]["situacion_maxima"] == 4
    # Histórico: solo la situación 3 es desvío; la 1 (normal) y la 0 (sin deuda) no.
    assert res["historico"]["periodos_analizados"] == 2
    assert res["historico"]["desvios"] == [
        {"periodo": "202403", "entidad": "BANCO Z", "situacion": 3}
    ]
