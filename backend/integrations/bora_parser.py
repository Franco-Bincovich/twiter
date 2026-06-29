"""Parseo del HTML de dateas.com (extraído de `bora_client` por el límite de líneas).

Funciones puras de parseo con BeautifulSoup: separan TODO el conocimiento del HTML de
dateas del transporte HTTP (`bora_client`). Sin red ni I/O: reciben HTML y devuelven datos.

dateas tiene tres bloques estables (confirmados con datos reales, ej. CUIT 30549738644):
Datos Básicos y de Identificación, Información de ARCA (ambos en `table.entity-table-vertical`,
filas th/td) y Boletines Oficiales (`div.search-result` por publicación). El parser devuelve
strings crudos; la normalización (mapeos, fechas, nivel de alerta) vive en `bora_normalizer`.
"""

import re

from bs4 import BeautifulSoup

_BASE_URL = "https://www.dateas.com"
_MAX_PUBLICACIONES = 10
_RE_FECHA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_RE_SECCION = re.compile(r"(\w+ Secci[oó]n)", re.IGNORECASE)


def _tabla_a_dict(tabla) -> dict:
    """Convierte una tabla th/td vertical en {etiqueta: valor}, quitando links anidados."""
    filas = {}
    for tr in tabla.find_all("tr"):
        th, td = tr.find("th"), tr.find("td")
        if not th or not td:
            continue
        for a in td.find_all("a"):
            a.extract()  # remueve "Ver Informe Completo" y otros links del valor
        filas[th.get_text(strip=True)] = td.get_text(" ", strip=True) or None
    return filas


def _tablas_verticales(soup: BeautifulSoup) -> list:
    """Devuelve las tablas de datos verticales en orden (0 = básicos, 1 = ARCA)."""
    return soup.find_all("table", class_="entity-table-vertical")


def extraer_datos_basicos(soup: BeautifulSoup) -> dict:
    """Extrae el bloque 'Datos Básicos y de Identificación' (primera tabla vertical)."""
    tablas = _tablas_verticales(soup)
    tabla = _tabla_a_dict(tablas[0]) if tablas else {}
    nombre = soup.find("span", attrs={"itemprop": "name"})
    return {
        "razon_social": (nombre.get_text(strip=True) if nombre else None) or tabla.get("Razón Social"),
        "cuit": tabla.get("CUIT"),
        "ubicacion": tabla.get("Ubicación"),
        "situacion_crediticia_resumen": tabla.get("Situación crediticia"),
    }


def extraer_datos_arca(soup: BeautifulSoup) -> dict:
    """Extrae el bloque 'Información de ARCA' (segunda tabla vertical). Valores crudos."""
    tablas = _tablas_verticales(soup)
    tabla = _tabla_a_dict(tablas[1]) if len(tablas) > 1 else {}
    return {
        "actividad": tabla.get("Actividad u Ocupación"),
        "ganancias": tabla.get("Ganancias"),
        "iva": tabla.get("IVA"),
        "monotributo": tabla.get("Monotributo"),
        "integra_sociedades": tabla.get("Integra Sociedades"),
        "empleador": tabla.get("Empleador"),
    }


def _parsear_publicacion(resultado) -> dict:
    """Convierte un `div.search-result` en {titulo, url, snippet, fecha (ISO), seccion}."""
    h4 = resultado.find("h4")
    ancla = h4.find("a") if h4 else None
    snippet = resultado.find("p", class_="search-result-snippet")
    titulo = h4.get_text(" ", strip=True) if h4 else ""
    href = ancla.get("href") if ancla else None
    fecha_match = _RE_FECHA.search(titulo)
    seccion_match = _RE_SECCION.search(titulo)
    return {
        "titulo": titulo or None,
        "url": f"{_BASE_URL}{href}" if href and href.startswith("/") else href,
        "snippet": snippet.get_text(" ", strip=True) if snippet else None,
        "fecha": f"{fecha_match.group(3)}-{fecha_match.group(2)}-{fecha_match.group(1)}" if fecha_match else None,
        "seccion": seccion_match.group(1) if seccion_match else None,
    }


def extraer_publicaciones_bora(soup: BeautifulSoup) -> list:
    """Extrae las publicaciones del bloque de Boletines Oficiales (máx 10, orden del HTML)."""
    resultados = soup.find_all("div", class_="search-result")[:_MAX_PUBLICACIONES]
    return [_parsear_publicacion(r) for r in resultados]


def extraer_todo(html: str) -> dict:
    """Parsea el HTML de dateas y devuelve los tres bloques combinados.

    Args:
        html: HTML de la página de la empresa en dateas (`/es/empresa/{slug}-{cuit}`).

    Returns:
        Dict con 'datos_basicos', 'datos_arca' y 'publicaciones_bora' (valores crudos).
    """
    soup = BeautifulSoup(html, "html.parser")
    return {
        "datos_basicos": extraer_datos_basicos(soup),
        "datos_arca": extraer_datos_arca(soup),
        "publicaciones_bora": extraer_publicaciones_bora(soup),
    }
