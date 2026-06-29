"""Tests del Agente BORA: cliente (slug), servicio (mockeado) y normalizador/parser.

NO se le pega a dateas.com: se mockea `bora_client.obtener_datos` con monkeypatch. Se usa
asyncio.run para no depender de plugins async de pytest. El normalizador y el parser se
prueban como funciones puras (el parser, sobre un HTML fixture con la estructura real de
dateas: dos `table.entity-table-vertical` y varios `div.search-result`).
"""

import asyncio

import pytest

from integrations import bora_client, bora_parser
from services import bora_normalizer, bora_service
from utils.errors import AppError

CUIT = "30549738644"
RAZON = "CRISTEM S A"

# `raw` tal como lo devuelve `bora_client.obtener_datos` (salida de bora_parser.extraer_todo).
RAW = {
    "datos_basicos": {
        "razon_social": "CRISTEM S A",
        "cuit": "30-54973864-4",
        "ubicacion": "Quilmes, Buenos Aires (Pcia)",
        "situacion_crediticia_resumen": "Hay 92 calificaciones crediticias en el BCRA",
    },
    "datos_arca": {
        "actividad": "Fabricación de productos de vidrio n.c.p.",
        "ganancias": "Activo", "iva": "Activo", "monotributo": "No Inscripto",
        "integra_sociedades": "No", "empleador": "Si",
    },
    "publicaciones_bora": [
        {
            "titulo": "Boletín Oficial de la República Argentina del 16/03/2022 - Cuarta Sección - Página 5",
            "url": "https://www.dateas.com/es/docs/boletin/2022/03/16",
            "snippet": "Publicación de edicto societario", "fecha": "2022-03-16",
            "seccion": "Cuarta Sección",
        }
    ],
}

# HTML fixture con la estructura real de dateas (dos tablas verticales + publicaciones).
HTML_DATEAS = """
<table class="entity-table entity-table-vertical entity-table-no-adsense">
  <tr><th>Razón Social</th><td><span itemprop="name">CRISTEM S A</span><a href="/x">Ver Informe Completo</a></td></tr>
  <tr><th>CUIT</th><td>30-54973864-4</td></tr>
  <tr><th>Ubicación</th><td>Quilmes, Buenos Aires (Pcia)</td></tr>
  <tr><th>Situación crediticia</th><td>Hay 92 calificaciones crediticias</td></tr>
</table>
<table class="entity-table entity-table-vertical entity-table-no-adsense">
  <tr><th>Actividad u Ocupación</th><td>Fabricación de productos de vidrio n.c.p.</td></tr>
  <tr><th>Ganancias</th><td>Activo</td></tr>
  <tr><th>IVA</th><td>Activo</td></tr>
  <tr><th>Monotributo</th><td>No Inscripto</td></tr>
  <tr><th>Integra Sociedades</th><td>No</td></tr>
  <tr><th>Empleador</th><td>Si</td></tr>
</table>
<div class="search-result">
  <h4><a href="/es/docs/boletin-4ta/2022/03/16?page=5">Boletín Oficial de la República Argentina del 16/03/2022 - Cuarta Sección - Página 5</a></h4>
  <p class="search-result-snippet">Publicación de edicto societario de la empresa</p>
</div>
<div class="search-result">
  <h4><a href="/es/docs/boletin-4ta/2021/01/25?page=4">Boletín Oficial de la República Argentina del 25/01/2021 - Cuarta Sección - Página 4</a></h4>
  <p class="search-result-snippet">Otra publicación de la sociedad</p>
</div>
"""


def _mockear(monkeypatch, *, datos):
    """Mockea bora_client.obtener_datos (cuit, razon_social) con un valor o excepción fijos."""
    async def _resolver(cuit, razon_social):
        if isinstance(datos, BaseException):
            raise datos
        return datos

    monkeypatch.setattr(bora_service.bora_client, "obtener_datos", _resolver)


def _publicacion(snippet="edicto", titulo="Boletín del 01/02/2020 - Primera Sección"):
    """Arma una publicación cruda mínima para los tests del normalizador."""
    return {"titulo": titulo, "url": "u", "snippet": snippet, "fecha": "2020-02-01", "seccion": "Primera Sección"}


def test_construir_url_genera_url():
    assert bora_client.construir_url("30549738644", "CRISTEM S A") == (
        "https://www.dateas.com/es/empresa/cristem-s-a-30549738644"
    )


def test_obtener_datos_bora_cuit_valido(monkeypatch):
    _mockear(monkeypatch, datos=RAW)

    datos = asyncio.run(bora_service.obtener_datos_bora(CUIT, RAZON))

    assert datos["razon_social"] == "Cristem S A"  # title-case
    assert datos["ubicacion"] == "Quilmes, Buenos Aires (Pcia)"
    assert datos["datos_arca"]["ganancias"] == "activo"  # mapeado por el normalizer
    assert datos["datos_arca"]["monotributo"] == "no_inscripto"
    assert datos["datos_arca"]["empleador"] is True
    assert datos["nivel_alerta"] == "medio"  # hay 1 publicación no crítica


def test_obtener_datos_bora_cuit_no_encontrado(monkeypatch):
    # La página no existe (404 → obtener_datos None) → BORA_CUIT_NOT_FOUND.
    _mockear(monkeypatch, datos=None)

    with pytest.raises(AppError) as exc:
        asyncio.run(bora_service.obtener_datos_bora(CUIT, RAZON))
    assert exc.value.code == "BORA_CUIT_NOT_FOUND"
    assert exc.value.status_code == 404


def test_obtener_datos_bora_source_unavailable(monkeypatch):
    # Si la fuente cae (BORA_UNAVAILABLE desde el cliente), el error se propaga.
    _mockear(monkeypatch, datos=AppError("BORA no disponible", "BORA_UNAVAILABLE", 503))

    with pytest.raises(AppError) as exc:
        asyncio.run(bora_service.obtener_datos_bora(CUIT, RAZON))
    assert exc.value.code == "BORA_UNAVAILABLE"
    assert exc.value.status_code == 503


def test_normalizer_nivel_alerta_bajo():
    # Sin publicaciones en el BORA → nivel "bajo".
    datos = bora_normalizer.normalizar({"publicaciones_bora": []})
    assert datos["nivel_alerta"] == "bajo"
    assert datos["alertas_criticas"] == []


def test_normalizer_nivel_alerta_medio():
    # Hay publicaciones pero ninguna crítica → nivel "medio".
    datos = bora_normalizer.normalizar({"publicaciones_bora": [_publicacion(snippet="designación de autoridades")]})
    assert datos["nivel_alerta"] == "medio"
    assert datos["alertas_criticas"] == []


def test_normalizer_nivel_alerta_alto():
    # Una publicación con "concurso" en el snippet → nivel "alto" y alerta crítica registrada.
    pub = _publicacion(snippet="se decreta el concurso preventivo de la firma")
    datos = bora_normalizer.normalizar({"publicaciones_bora": [pub]})
    assert datos["nivel_alerta"] == "alto"
    assert len(datos["alertas_criticas"]) == 1


def test_normalizer_empleador_bool():
    activo = bora_normalizer.normalizar({"datos_arca": {"empleador": "Si"}})
    inactivo = bora_normalizer.normalizar({"datos_arca": {"empleador": "No"}})
    assert activo["datos_arca"]["empleador"] is True
    assert inactivo["datos_arca"]["empleador"] is False


def test_parser_extrae_publicaciones():
    raw = bora_parser.extraer_todo(HTML_DATEAS)
    pubs = raw["publicaciones_bora"]
    assert len(pubs) == 2
    assert pubs[0]["fecha"] == "2022-03-16"  # parseada del título dd/mm/aaaa → ISO
    assert pubs[0]["seccion"] == "Cuarta Sección"
    assert pubs[0]["url"] == "https://www.dateas.com/es/docs/boletin-4ta/2022/03/16?page=5"
    assert "edicto societario" in pubs[0]["snippet"]


def test_parser_extrae_tablas():
    raw = bora_parser.extraer_todo(HTML_DATEAS)
    assert raw["datos_basicos"]["razon_social"] == "CRISTEM S A"  # link "Ver Informe..." removido
    assert raw["datos_basicos"]["cuit"] == "30-54973864-4"
    assert raw["datos_arca"]["actividad"] == "Fabricación de productos de vidrio n.c.p."
    assert raw["datos_arca"]["empleador"] == "Si"  # crudo; el normalizer lo pasa a bool
