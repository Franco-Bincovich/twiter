"""Generación de slugs url-friendly a partir de texto libre (razón social, etc.).

Extraído como utilidad compartida para que los clients que construyen URLs de detalle
por slug (BORA y, a futuro, ARCA) no dupliquen la lógica.
"""

import re
import unicodedata


def generar_slug(texto: str) -> str:
    """Convierte un texto a slug: minúsculas, sin acentos, espacios→guiones, sin símbolos.

    Args:
        texto: Texto libre a slugificar (ej. razón social de la empresa).

    Returns:
        El slug: minúsculas, acentos transliterados a ASCII, espacios y símbolos colapsados
        en guiones simples, sin guiones al inicio/fin (ej. 'CRISTEM S A' → 'cristem-s-a').
    """
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", ascii_))).strip("-")
