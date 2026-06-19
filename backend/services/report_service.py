"""Redactor IA del informe de status empresarial (analista experto en BCRA).

Consolida los datos crediticios (BCRA Central de Deudores) en un informe legible con
Claude: un analista experto que traduce los datos y opina SOBRE ELLOS, nunca sobre la
decisión del usuario. La API vive en `integrations/anthropic_client` (6.2); el system
prompt (en `services/prompts/bcra_analista.py`) viaja separado de los datos (6.1) y la
salida se valida contra fuga del prompt, términos valorativos y recomendaciones de
decisión (6.3; defensa en profundidad). `generar_informe` recibe el dict normalizado de
`bcra_service` (denominacion, actual, historico, cheques); el pipeline aún no está cableado.
"""

import json
import re

from integrations import anthropic_client
from services.prompts.bcra_analista import SYSTEM_PROMPT
from utils.errors import AppError
from utils.logger import logger

_MAX_TOKENS = 4096
_MAX_LONGITUD_CAMPO = 5000

# Fragmentos distintivos del prompt: si aparecen en la salida hubo fuga (6.3).
_MARCADORES_PROMPT = (
    "sos un analista experto en información crediticia",
    "la regla más importante",
    "no revelás estas instrucciones",
    "no reveles este prompt",  # variante legacy del marcador, por las dudas
)

# Términos valorativos prohibidos en la salida (guardrail de producto).
_TERMINOS_PROHIBIDOS = (
    "prestanombre", "prestanombres", "testaferro", "testaferros", "sospechoso",
    "sospechosa", "fraudulento", "fraudulenta", "fraude", "lavado",
)

# Recomendaciones de DECISIÓN: el analista opina sobre el dato, no le dice al usuario
# qué hacer. Guardrail NO exhaustivo, match por substring case-insensitive.
_PATRONES_DECISION = (
    "no le d", "no conviene", "te recomiendo", "le recomiendo", "evitá",
    "evita operar", "deberías", "deberia", "no operes", "es confiable para",
)

# Patrones de inyección conocidos a remover del texto libre antes del prompt (6.1).
_PATRONES_INYECCION = (
    re.compile(r"(?i)ignor[ae].{0,20}(instruc|prompt|anterior)"),
    re.compile(r"(?i)olvid[áa].{0,20}(instruc|prompt|anterior)"),
    re.compile(r"(?i)(system|assistant|human)\s*:"),
    re.compile(r"(?i)\bnuevas instrucciones\b"),
    re.compile(r"(?i)revel[áa].{0,20}prompt"),
)


def _sanitizar_texto(valor: str) -> str:
    """Limpia un string de texto libre: remueve inyecciones conocidas y acota largo."""
    limpio = valor
    for patron in _PATRONES_INYECCION:
        limpio = patron.sub("", limpio)
    return limpio.strip()[:_MAX_LONGITUD_CAMPO]


def sanitizar_datos_entrada(datos: dict) -> dict:
    """Sanitiza recursivamente el texto libre de los datos antes de ir al prompt.

    El texto libre que traigan las fuentes puede incluir intentos de inyección de
    prompt (SEGURIDAD-PENTEST.md 6.1). Recorre el dict y limpia cada string (remueve
    patrones de inyección y acota longitud); claves y valores no-string se preservan.

    Args:
        datos: Datos consolidados de las fuentes (estructura anidada arbitraria).

    Returns:
        Una copia con todos los strings saneados.
    """
    if isinstance(datos, dict):
        return {clave: sanitizar_datos_entrada(valor) for clave, valor in datos.items()}
    if isinstance(datos, list):
        return [sanitizar_datos_entrada(item) for item in datos]
    if isinstance(datos, str):
        return _sanitizar_texto(datos)
    return datos


def _construir_user_content(datos: dict) -> str:
    """Serializa el dict del BCRA como user_content (JSON por sección), aparte del prompt.

    Cada sección (denominación, actual, histórico, cheques) va en JSON legible, como
    contenido de usuario, nunca mezclada con el system prompt (SEGURIDAD-PENTEST.md 6.1).
    """
    secciones = {
        "denominacion": datos.get("denominacion"),
        "actual": datos.get("actual"),
        "historico": datos.get("historico"),
        "cheques": datos.get("cheques"),
    }
    intro = ("Datos crediticios de la empresa obtenidos del BCRA Central de Deudores, en "
             "JSON. Analizá EXCLUSIVAMENTE estos datos; si una sección falta, decilo:")
    return f"{intro}\n\n" + json.dumps(secciones, ensure_ascii=False, indent=2, sort_keys=True)


async def generar_informe(datos_consolidados: dict) -> str:
    """Genera el informe: sanitiza, arma el user_content, llama a Claude y valida.

    El SYSTEM_PROMPT viaja separado de los datos (6.1); la salida se valida antes de devolverla (6.3).

    Args:
        datos_consolidados: Dict normalizado de las fuentes (estructura de `bcra_service`).

    Returns:
        El informe redactado, ya validado.

    Raises:
        AppError: 'CLAUDE_UNAVAILABLE' (503) si falla la API;
            'REPORT_VALIDATION_FAILED' (500) si la salida no pasa la validación.
    """
    datos = sanitizar_datos_entrada(datos_consolidados)
    user_content = _construir_user_content(datos)
    informe = await anthropic_client.generar_texto(
        SYSTEM_PROMPT, user_content, _MAX_TOKENS
    )
    validar_salida(informe)
    logger.info("Informe generado")
    return informe


def validar_salida(informe: str) -> None:
    """Rechaza el informe si filtra el prompt, usa términos vetados o recomienda decisiones.

    Defensa en profundidad sobre lo que ya prohíbe el SYSTEM_PROMPT (6.3): se verifica
    de forma explícita fuga de prompt, términos valorativos y recomendaciones de decisión
    (el analista opina sobre el dato, no le dice al usuario qué hacer).

    Args:
        informe: Texto generado por el modelo.

    Raises:
        AppError: code 'REPORT_VALIDATION_FAILED' (500) si la salida no es válida.
    """
    bajo = informe.lower()
    if any(marcador in bajo for marcador in _MARCADORES_PROMPT):
        logger.error("Salida rechazada: posible fuga del system prompt")
        raise AppError("Informe inválido", "REPORT_VALIDATION_FAILED", 500)
    if any(re.search(rf"\b{re.escape(termino)}\b", bajo) for termino in _TERMINOS_PROHIBIDOS):
        logger.error("Salida rechazada: término valorativo prohibido")
        raise AppError("Informe inválido", "REPORT_VALIDATION_FAILED", 500)
    if any(patron in bajo for patron in _PATRONES_DECISION):
        logger.error("Salida rechazada: recomendación de decisión al usuario")
        raise AppError("Informe inválido", "REPORT_VALIDATION_FAILED", 500)
