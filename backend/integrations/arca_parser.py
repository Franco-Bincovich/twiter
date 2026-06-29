"""Parseo de la constancia de cuitonline.com (extraído de `arca_client`).

Funciones puras de parseo con BeautifulSoup: separan TODO el conocimiento del HTML de
cuitonline del transporte HTTP (`arca_client`). Sin red ni I/O: reciben HTML y devuelven
datos.

IMPORTANTE: el body del detalle está bloqueado por un paywall de adblocker, así que los
datos NO se leen del cuerpo de la página. Se parsean ÚNICAMENTE de los meta tags
`<meta name="description">` (campos separados por un punto medio) y `<meta name="keywords">`
(empleador y tipo de persona). Calibrado contra datos reales (ej. CUIT 30549738644).

SEPARADOR: cuitonline sirve el `·` corrupto en origen (bytes EF BF BD), así que tras
decodificar como UTF-8 llega como U+FFFD (replacement char) y es irrecuperable desde los
bytes. Por eso el split acepta tanto U+FFFD (lo real) como U+00B7 `·` (fallback por si lo
corrigen), 1+ veces y comiéndose los espacios alrededor. Se arma con chr() para no meter
caracteres no-ASCII en el fuente.
"""

import re

from bs4 import BeautifulSoup

_SEPARADOR = re.compile(r"\s*[" + chr(0xFFFD) + chr(0x00B7) + r"]+\s*")


def _meta(soup: BeautifulSoup, nombre: str) -> str | None:
    """Devuelve el `content` del `<meta name="...">` pedido, o None si no está."""
    tag = soup.find("meta", attrs={"name": nombre})
    return tag.get("content") if tag and tag.get("content") else None


def _parsear_descripcion(descripcion: str) -> dict:
    """Parsea el meta description (campos separados por U+FFFD/`·`) a un dict crudo.

    El primer campo es siempre la razón social. El resto se identifica por prefijo
    ('CUIT: ', 'Localidad: ', 'Fecha de contrato social: ', 'Ganancias: ', 'IVA: ') o por
    contenido (tipo de persona); el primer campo libre sin rótulo se toma como domicilio.
    Defensivo ante campos ausentes o en otro orden.
    """
    partes = [p.strip() for p in _SEPARADOR.split(descripcion) if p.strip()]
    datos = {
        "razon_social": None, "cuit": None, "tipo_persona": None,
        "domicilio_fiscal": None, "localidad": None, "fecha_contrato_social": None,
        "condicion_ganancias": None, "condicion_iva": None,
    }
    if partes:
        datos["razon_social"] = partes[0]
    for parte in partes[1:]:
        bajo = parte.lower()
        if bajo.startswith("cuit:"):
            datos["cuit"] = parte.split(":", 1)[1].strip()
        elif bajo.startswith("persona jur"):
            datos["tipo_persona"] = "Persona Jurídica"
        elif bajo.startswith("persona f"):
            datos["tipo_persona"] = "Persona Física"
        elif bajo.startswith("localidad:"):
            datos["localidad"] = parte.split(":", 1)[1].strip()
        elif bajo.startswith("fecha de contrato social:"):
            datos["fecha_contrato_social"] = parte.split(":", 1)[1].strip()
        elif bajo.startswith("ganancias:"):
            datos["condicion_ganancias"] = parte.split(":", 1)[1].strip()
        elif bajo.startswith("iva:"):
            datos["condicion_iva"] = parte.split(":", 1)[1].strip()
        elif datos["domicilio_fiscal"] is None:
            datos["domicilio_fiscal"] = parte  # primer campo libre sin rótulo = domicilio
    return datos


def extraer_constancia(html: str) -> dict:
    """Extrae los campos crudos de la constancia desde los meta tags de la página.

    Args:
        html: HTML del detalle (`/detalle/{cuit}/{slug}.html`); solo se leen sus meta tags.

    Returns:
        Dict con los campos crudos (None si un campo no aparece). `es_empleador` es bool
        (sale del meta keywords). La normalización vive en `arca_normalizer`.
    """
    soup = BeautifulSoup(html, "html.parser")
    datos = _parsear_descripcion(_meta(soup, "description") or "")
    keywords = (_meta(soup, "keywords") or "").lower()
    datos["es_empleador"] = "empleador" in keywords
    # tipo_persona secundario desde keywords si el description no lo trajo (confirma/completa).
    if datos["tipo_persona"] is None:
        if "persona física" in keywords or "persona fisica" in keywords:
            datos["tipo_persona"] = "Persona Física"
        elif "persona jurídica" in keywords or "persona juridica" in keywords:
            datos["tipo_persona"] = "Persona Jurídica"
    return datos


def es_persona_fisica(raw: dict) -> bool:
    """True si el tipo_persona parseado de los meta tags es de una persona física."""
    tipo = (raw or {}).get("tipo_persona") or ""
    return tipo.strip().lower().startswith("persona f")
