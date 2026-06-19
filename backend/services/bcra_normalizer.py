"""Normalización de las respuestas crudas del BCRA a dicts estables.

Extraído de `bcra_service` para respetar el límite de líneas: el servicio orquesta
los tres endpoints y este módulo traduce cada bloque (deuda actual, histórico y
cheques) a la forma que consume el resto del producto. Sin HTTP ni I/O: funciones
puras sobre los `results` que entrega `integrations/bcra_client`.

Reglas de monto confirmadas con datos reales: las deudas vienen en MILES de pesos
(se multiplican ×1000); los cheques vienen en PESOS reales (no se tocan).
"""

_MILES = 1000  # las deudas del BCRA se informan en miles de pesos; ×1000 = pesos reales

# Flag normalizado -> campo crudo del BCRA que lo activa (truthy).
_FLAGS = {
    "situacion_juridica": "situacionJuridica",
    "proceso_judicial": "procesoJud",
    "recategorizacion": "recategorizacionOblig",
    "refinanciaciones": "refinanciaciones",
    "irrecuperable": "irrecDisposicionTecnica",
}


def denominacion(*results: dict | None) -> str | None:
    """Devuelve la primera denominación disponible entre los results recibidos.

    Args:
        *results: Los `results` de los tres endpoints, en cualquier orden (o None).

    Returns:
        La denominación social, o None si ninguno la trajo.
    """
    for res in results:
        if res and res.get("denominacion"):
            return res["denominacion"]
    return None


def _a_float(valor) -> float:
    """Convierte a float tolerando None (lo trata como 0.0)."""
    return float(valor) if valor is not None else 0.0


def normalizar_actual(deudas: dict | None) -> dict:
    """Normaliza la deuda ACTUAL: peor situación, totales y flags del último periodo.

    Toma el periodo más reciente (mayor 'AAAAMM'). `situacion_maxima` es el peor
    número (más alto) entre sus entidades. `entidades_activas` ignora la situación 0
    (= sin deuda informada). Los montos pasan de miles a pesos reales (×1000).

    Args:
        deudas: `results` del endpoint de deudas, o None si no hubo datos (404).

    Returns:
        Dict con periodo, situacion_maxima, entidades_activas, deuda_total,
        entidades y flags_activos.
    """
    vacio = {
        "periodo": None, "situacion_maxima": None, "entidades_activas": 0,
        "deuda_total": 0.0, "entidades": [],
        "flags_activos": {flag: 0 for flag in _FLAGS},
    }
    periodos = (deudas or {}).get("periodos") or []
    if not periodos:
        return vacio

    reciente = max(periodos, key=lambda p: p.get("periodo") or "")
    crudas = reciente.get("entidades") or []
    entidades = [
        {
            "entidad": e.get("entidad"),
            "situacion": e.get("situacion"),
            # monto ×1000: el BCRA informa la deuda en miles de pesos.
            "monto": _a_float(e.get("monto")) * _MILES,
            "dias_atraso": e.get("diasAtrasoPago"),
            "fecha_sit1": e.get("fechaSit1"),
        }
        for e in crudas
    ]
    situaciones = [e["situacion"] for e in entidades if e["situacion"] is not None]
    return {
        "periodo": reciente.get("periodo"),
        "situacion_maxima": max(situaciones) if situaciones else None,
        "entidades_activas": sum(1 for s in situaciones if s != 0),
        "deuda_total": sum(e["monto"] for e in entidades),
        "entidades": entidades,
        "flags_activos": {
            flag: sum(1 for e in crudas if e.get(campo)) for flag, campo in _FLAGS.items()
        },
    }


def normalizar_historico(historicas: dict | None) -> dict:
    """Normaliza el histórico: cuenta periodos y marca desvíos (situación 2 a 5).

    Un desvío es una entidad con situación de riesgo (2 a 5 inclusive) en cualquier
    periodo. La situación 0 (sin deuda informada) y la 1 (normal) NO son desvíos: la
    0 es ausencia de deuda, no un deterioro de riesgo.

    Args:
        historicas: `results` del endpoint histórico, o None si no hubo datos (404).

    Returns:
        Dict con periodos_analizados y la lista de desvios [{periodo, entidad, situacion}].
    """
    periodos = (historicas or {}).get("periodos") or []
    desvios = [
        {"periodo": p.get("periodo"), "entidad": e.get("entidad"), "situacion": e.get("situacion")}
        for p in periodos
        for e in (p.get("entidades") or [])
        # solo 2..5 es desvío de riesgo; la 0 (sin deuda) y la 1 (normal) no lo son.
        if e.get("situacion") is not None and 2 <= e["situacion"] <= 5
    ]
    return {"periodos_analizados": len(periodos), "desvios": desvios}


def normalizar_cheques(cheques: dict | None) -> dict:
    """Normaliza los cheques rechazados a agregados (estructura causal→entidad→detalle).

    Recorre los tres niveles y devuelve solo agregados: nunca el detalle completo de
    cada cheque (tope defensivo ante cientos de registros). Los montos vienen en
    pesos reales: NO se multiplican (a diferencia de las deudas).

    Args:
        cheques: `results` del endpoint de cheques, o None si no hubo datos (404).

    Returns:
        Dict con tiene_cheques, total_cheques, total_pagados, monto_total,
        mayor_cheque y por_causal.
    """
    causales = (cheques or {}).get("causales") or []
    montos: list[float] = []
    pagados = 0
    por_causal: dict[str, int] = {}
    for bloque in causales:
        detalles = [d for ent in (bloque.get("entidades") or []) for d in (ent.get("detalle") or [])]
        causal = bloque.get("causal")
        por_causal[causal] = por_causal.get(causal, 0) + len(detalles)
        for d in detalles:
            montos.append(_a_float(d.get("monto")))  # cheques: pesos reales, sin ×1000
            if d.get("fechaPago") is not None:
                pagados += 1
    return {
        "tiene_cheques": bool(montos),
        "total_cheques": len(montos),
        "total_pagados": pagados,
        "monto_total": sum(montos),
        "mayor_cheque": max(montos) if montos else 0.0,
        "por_causal": por_causal,
    }
