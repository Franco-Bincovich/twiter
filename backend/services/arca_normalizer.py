"""Normalización de los campos crudos del scraping de ARCA a un dict estable.

Funciones puras (sin HTTP ni I/O), patrón espejo de `bcra_normalizer`: el service
orquesta y este módulo limpia y estructura cada campo del scraping.
"""

import re
from datetime import datetime

# Formatos de fecha que sabemos parsear desde el scraping; el primero que matchea gana.
_FORMATOS_FECHA = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y")

# Valores crudos interpretados como "sí" en campos booleanos (ej. es_empleador).
_VERDADERO = {"si", "sí", "true", "1", "s", "empleador"}

_ALERTA = {"dado_de_baja": "alto", "inactivo": "medio", "activo": "bajo"}  # estado -> alerta


def _titulo(valor) -> str | None:
    """strip + title-case de un string; None si viene vacío o no es string."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    return valor.strip().title()


def _a_bool(valor) -> bool:
    """Convierte a bool tolerando string ('SI'/'NO'/'true'...) o bool ya tipado."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        return valor.strip().lower() in _VERDADERO
    return False


def _normalizar_estado(valor) -> str | None:
    """Normaliza el estado de inscripción a activo | inactivo | dado_de_baja | None."""
    if not isinstance(valor, str):
        return None
    bajo = valor.strip().lower()
    if "baja" in bajo:
        return "dado_de_baja"
    if "inactiv" in bajo:
        return "inactivo"
    if "activ" in bajo:
        return "activo"
    return None


def _a_iso(valor) -> str | None:
    """Parsea una fecha conocida a ISO 8601 (YYYY-MM-DD); None si no se reconoce."""
    if isinstance(valor, str):
        crudo = valor.strip()
        for fmt in _FORMATOS_FECHA:
            try:
                return datetime.strptime(crudo, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _parsear_regimen(item) -> dict:
    """Convierte un régimen crudo (string 'nombre + fecha' o dict) a {nombre, fecha_desde}."""
    if isinstance(item, dict):
        return {"nombre": item.get("nombre"), "fecha_desde": _a_iso(item.get("fecha_desde"))}
    if isinstance(item, str):
        fecha = re.search(r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}", item)
        if fecha:
            nombre = re.sub(r"(?i)\s*(desde|vigente|a partir de)\s*$", "", item.replace(fecha.group(), "")).strip(" .-")
            return {"nombre": nombre or None, "fecha_desde": _a_iso(fecha.group())}
        return {"nombre": item.strip() or None, "fecha_desde": None}
    return {"nombre": None, "fecha_desde": None}


def normalizar(raw: dict) -> dict:
    """Limpia y estructura los campos crudos del scraping de ARCA.

    Args:
        raw: Dict crudo de `arca_client.obtener_constancia`.

    Returns:
        Dict estable: razon_social title-case, estado/fecha normalizados, nivel_alerta y resto.
    """
    estado = _normalizar_estado(raw.get("estado_inscripcion"))
    regimenes = raw.get("regimenes") or []
    return {
        "razon_social": _titulo(raw.get("razon_social")),
        "cuit": raw.get("cuit"),
        "tipo_persona": raw.get("tipo_persona"),
        "domicilio_fiscal": raw.get("domicilio_fiscal"),
        "localidad": raw.get("localidad"),
        "actividad_principal": raw.get("actividad_principal"),
        "actividades_secundarias": raw.get("actividades_secundarias") or [],
        "condicion_iva": raw.get("condicion_iva"),
        "condicion_ganancias": raw.get("condicion_ganancias"),
        "estado_inscripcion": estado,
        "es_empleador": _a_bool(raw.get("es_empleador")),
        "fecha_contrato_social": _a_iso(raw.get("fecha_contrato_social")),
        "regimenes": [_parsear_regimen(r) for r in regimenes],
        "nivel_alerta": _ALERTA.get(estado, "medio"),
    }
