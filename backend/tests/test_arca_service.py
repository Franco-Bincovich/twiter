"""Tests del Agente ARCA: servicio (services/arca_service.py) y normalizador.

NO se le pega a cuitonline.com: se mockea `arca_client` (sus dos funciones async) con
monkeypatch. Se usa asyncio.run para no depender de plugins async de pytest, igual que
el resto de la suite. El normalizador se prueba como función pura sobre dicts crudos
sintéticos (no depende del HTML real ni del cliente).
"""

import asyncio

import pytest

from integrations import arca_client, arca_parser
from services import arca_normalizer, arca_service
from utils.errors import AppError

CUIT = "30549738644"
RAZON = "CRISTEM S A"

# `raw` tal como lo devuelve ahora el parser desde los meta tags (no del body, que está
# bajo paywall). Datos reales de CRISTEM S.A. El meta no trae estado_inscripcion ni
# regímenes ni actividad: esos campos quedan en None/[] y nivel_alerta cae a "medio".
RAW = {
    "razon_social": "CRISTEM S A",
    "cuit": CUIT,
    "tipo_persona": "Persona Jurídica",
    "domicilio_fiscal": "rodolfo a lopez 2539",
    "localidad": "Quilmes",
    "fecha_contrato_social": "1988-08-24",
    "condicion_ganancias": "Ganancias Sociedades",
    "condicion_iva": None,
    "es_empleador": True,
}

# HTML real reducido a sus meta tags (el body está bloqueado por el paywall de adblocker).
# OJO: el separador real que sirve cuitonline NO es "·": llega corrupto como U+FFFD al
# decodificar UTF-8 (ver arca_parser). Se reconstruye con chr(0xFFFD) para reproducir el
# caso real que rompía el parseo (razon_social se quedaba con TODO el string).
_SEP = f" {chr(0xFFFD)} "
_DESC_CRISTEM = _SEP.join([
    "CRISTEM S A",
    "CUIT: 30549738644",
    "Persona Jurídica",
    "rodolfo a lopez 2539",
    "Localidad: Quilmes",
    "Fecha de contrato social: 1988-08-24",
    "Ganancias: Ganancias Sociedades",
])
HTML_CRISTEM = (
    '<html><head>'
    f'<meta name="description" content="{_DESC_CRISTEM}">'
    '<meta name="keywords" content="cristem s a, persona jurídica, empleador, cuit, '
    'deudas de cristem s a, constancia de inscripción de cristem s a">'
    '</head><body>contenido bloqueado por paywall</body></html>'
)


def _mockear(monkeypatch, *, constancia):
    """Mockea arca_client.obtener_constancia (única llamada async del flujo ARCA).

    `construir_url` es pura y corre de verdad; solo se simula la descarga del detalle.
    """
    async def _resolver(_url):
        if isinstance(constancia, BaseException):
            raise constancia
        return constancia

    monkeypatch.setattr(arca_service.arca_client, "obtener_constancia", _resolver)


def test_construir_url_genera_slug():
    # El slug se arma desde la razón social: minúsculas, sin símbolos, espacios→guiones.
    assert arca_client.construir_url("30549738644", "CRISTEM S A") == (
        "https://www.cuitonline.com/detalle/30549738644/cristem-s-a.html"
    )
    assert arca_client.construir_url("30111111110", "CLINICA PRIVADA RANELAGH S.A.") == (
        "https://www.cuitonline.com/detalle/30111111110/clinica-privada-ranelagh-sa.html"
    )


def test_obtener_datos_arca_cuit_valido(monkeypatch):
    _mockear(monkeypatch, constancia=RAW)

    datos = asyncio.run(arca_service.obtener_datos_arca(CUIT, RAZON))

    assert datos["razon_social"] == "Cristem S A"  # title-case de "CRISTEM S A"
    assert datos["cuit"] == CUIT
    assert datos["tipo_persona"] == "Persona Jurídica"
    assert datos["domicilio_fiscal"] == "rodolfo a lopez 2539"
    assert datos["localidad"] == "Quilmes"  # propagada por el normalizer
    assert datos["es_empleador"] is True
    assert datos["fecha_contrato_social"] == "1988-08-24"  # ISO ya en el meta
    assert datos["condicion_ganancias"] == "Ganancias Sociedades"
    # El meta no trae estado de inscripción: nivel_alerta cae a "medio" (conservador).
    assert datos["estado_inscripcion"] is None
    assert datos["nivel_alerta"] == "medio"


def test_parser_extrae_de_meta_description():
    # Parseo desde los meta tags reales (no del body, bloqueado por paywall).
    raw = arca_parser.extraer_constancia(HTML_CRISTEM)
    assert raw["razon_social"] == "CRISTEM S A"
    assert raw["cuit"] == "30549738644"
    assert raw["tipo_persona"] == "Persona Jurídica"
    assert raw["domicilio_fiscal"] == "rodolfo a lopez 2539"
    assert raw["localidad"] == "Quilmes"
    assert raw["fecha_contrato_social"] == "1988-08-24"
    assert raw["condicion_ganancias"] == "Ganancias Sociedades"
    assert raw["es_empleador"] is True  # "empleador" está en el meta keywords
    assert arca_parser.es_persona_fisica(raw) is False


def test_parser_detecta_persona_fisica():
    html = (
        '<meta name="description" content="JUAN PEREZ · CUIT: 20123456786 · '
        'Persona Física · calle falsa 123">'
        '<meta name="keywords" content="juan perez, persona física, cuit">'
    )
    raw = arca_parser.extraer_constancia(html)
    assert raw["tipo_persona"] == "Persona Física"
    assert raw["es_empleador"] is False  # sin "empleador" en keywords
    assert arca_parser.es_persona_fisica(raw) is True


def test_obtener_datos_arca_cuit_no_encontrado(monkeypatch):
    # El detalle no existe (404 → obtener_constancia None) → ARCA_CUIT_NOT_FOUND.
    _mockear(monkeypatch, constancia=None)

    with pytest.raises(AppError) as exc:
        asyncio.run(arca_service.obtener_datos_arca(CUIT, RAZON))
    assert exc.value.code == "ARCA_CUIT_NOT_FOUND"
    assert exc.value.status_code == 404


def test_obtener_datos_arca_source_unavailable(monkeypatch):
    # Si la fuente cae (ARCA_UNAVAILABLE desde el cliente), el error se propaga.
    _mockear(monkeypatch, constancia=AppError("ARCA no disponible", "ARCA_UNAVAILABLE", 503))

    with pytest.raises(AppError) as exc:
        asyncio.run(arca_service.obtener_datos_arca(CUIT, RAZON))
    assert exc.value.code == "ARCA_UNAVAILABLE"
    assert exc.value.status_code == 503


def test_normalizer_estado_activo():
    datos = arca_normalizer.normalizar({"estado_inscripcion": "Activo", "es_empleador": "NO"})
    assert datos["estado_inscripcion"] == "activo"
    assert datos["nivel_alerta"] == "bajo"
    assert datos["es_empleador"] is False


def test_normalizer_estado_dado_de_baja():
    datos = arca_normalizer.normalizar({"estado_inscripcion": "Dado de Baja"})
    assert datos["estado_inscripcion"] == "dado_de_baja"
    assert datos["nivel_alerta"] == "alto"


def test_normalizer_fecha_iso():
    # Varios formatos reconocibles → ISO 8601; formato desconocido → None.
    assert arca_normalizer.normalizar({"fecha_contrato_social": "07/12/1999"})[
        "fecha_contrato_social"
    ] == "1999-12-07"
    assert arca_normalizer.normalizar({"fecha_contrato_social": "1999-12-07"})[
        "fecha_contrato_social"
    ] == "1999-12-07"
    assert arca_normalizer.normalizar({"fecha_contrato_social": "diciembre de 1999"})[
        "fecha_contrato_social"
    ] is None


def test_normalizer_nivel_alerta():
    # Un nivel por estado; estado desconocido/ausente → "medio" (conservador).
    assert arca_normalizer.normalizar({"estado_inscripcion": "Activo"})["nivel_alerta"] == "bajo"
    assert arca_normalizer.normalizar({"estado_inscripcion": "Inactivo"})["nivel_alerta"] == "medio"
    assert (
        arca_normalizer.normalizar({"estado_inscripcion": "Dado de baja"})["nivel_alerta"] == "alto"
    )
    assert arca_normalizer.normalizar({})["nivel_alerta"] == "medio"


def test_normalizer_regimenes_estructura():
    # Cada régimen crudo (string 'nombre + fecha') → {nombre, fecha_desde ISO}.
    datos = arca_normalizer.normalizar({"regimenes": ["Ganancias desde 01/04/2001", "Monotributo"]})
    assert datos["regimenes"] == [
        {"nombre": "Ganancias", "fecha_desde": "2001-04-01"},
        {"nombre": "Monotributo", "fecha_desde": None},
    ]
