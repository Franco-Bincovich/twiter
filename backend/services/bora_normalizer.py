"""Normalización de los datos crudos de dateas (BORA) a un dict estable.

Funciones puras (sin HTTP ni I/O), patrón espejo de `arca_normalizer`: el service orquesta
y este módulo limpia, mapea y estructura los tres bloques (datos básicos, ARCA, boletines).
"""

_MAX_PUBLICACIONES = 10

# Palabras que elevan el nivel de alerta a "alto" (en título o snippet de una publicación).
_CRITICAS = ("concurso", "quiebra")

# Valores crudos de ARCA → estado normalizado de inscripción impositiva.
_ESTADO = {"activo": "activo", "inactivo": "inactivo", "no inscripto": "no_inscripto"}


def _estado_impositivo(valor) -> str | None:
    """Mapea 'Activo'/'Inactivo'/'No Inscripto' → 'activo'/'inactivo'/'no_inscripto' (None si falta)."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    return _ESTADO.get(valor.strip().lower())


def _a_bool(valor) -> bool:
    """Convierte 'Si'/'No' (o bool) a bool; cualquier otra cosa → False."""
    if isinstance(valor, bool):
        return valor
    return isinstance(valor, str) and valor.strip().lower() in {"si", "sí", "true", "1"}


def _es_critica(pub: dict) -> bool:
    """True si la publicación menciona una palabra crítica (concurso/quiebra) en título o snippet."""
    texto = f"{pub.get('titulo') or ''} {pub.get('snippet') or ''}".lower()
    return any(palabra in texto for palabra in _CRITICAS)


def _normalizar_arca(arca: dict) -> dict:
    """Normaliza el bloque ARCA de dateas (estados impositivos + empleador bool)."""
    return {
        "actividad": (arca.get("actividad") or None),
        "ganancias": _estado_impositivo(arca.get("ganancias")),
        "iva": _estado_impositivo(arca.get("iva")),
        "monotributo": _estado_impositivo(arca.get("monotributo")),
        "empleador": _a_bool(arca.get("empleador")),
    }


def normalizar(raw: dict) -> dict:
    """Limpia y estructura los datos crudos de dateas (BORA) a un dict estable.

    Args:
        raw: Dict crudo de `bora_client.obtener_datos` (datos_basicos, datos_arca,
            publicaciones_bora).

    Returns:
        Dict estable con datos_basicos, datos_arca (mapeado), publicaciones (orden por fecha
        desc, máx 10), nivel_alerta ('alto' si hay concurso/quiebra, 'medio' si hay
        publicaciones, 'bajo' si no) y alertas_criticas (las que dispararon 'alto').
    """
    basicos = raw.get("datos_basicos") or {}
    publicaciones = list(raw.get("publicaciones_bora") or [])
    publicaciones.sort(key=lambda p: p.get("fecha") or "", reverse=True)
    publicaciones = publicaciones[:_MAX_PUBLICACIONES]
    criticas = [p for p in publicaciones if _es_critica(p)]
    if criticas:
        nivel = "alto"
    elif publicaciones:
        nivel = "medio"
    else:
        nivel = "bajo"
    return {
        "razon_social": (basicos.get("razon_social") or "").strip().title() or None,
        "cuit": basicos.get("cuit"),
        "ubicacion": basicos.get("ubicacion"),
        "situacion_crediticia_resumen": basicos.get("situacion_crediticia_resumen"),
        "datos_arca": _normalizar_arca(raw.get("datos_arca") or {}),
        "publicaciones": publicaciones,
        "nivel_alerta": nivel,
        "alertas_criticas": criticas,
    }
