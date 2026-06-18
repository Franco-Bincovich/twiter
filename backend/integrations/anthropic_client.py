"""Wrapper fino del SDK de Anthropic para generación de texto con Claude.

Aísla TODA llamada a la API de Anthropic (SEGURIDAD-PENTEST.md 6.2): el resto del
backend nunca importa el SDK directamente, solo este módulo. La API key se lee de
`settings`, nunca de `os.environ`. El system prompt viaja SIEMPRE en el parámetro
`system`, separado del contenido del usuario (6.1), de modo que los datos no puedan
alterar las instrucciones del asistente. Sin lógica de negocio: solo el transporte.
"""

from anthropic import AsyncAnthropic

from config.settings import settings
from utils.errors import AppError
from utils.logger import logger

# Claude Sonnet: mejor balance velocidad/inteligencia para la redacción del informe.
MODELO_CLAUDE = "claude-sonnet-4-6"

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)


async def generar_texto(system_prompt: str, user_content: str, max_tokens: int) -> str:
    """Genera texto con Claude a partir de un system prompt y contenido de usuario.

    Args:
        system_prompt: Instrucciones del asistente. Viajan en el parámetro `system`,
            SIEMPRE separadas de los datos (SEGURIDAD-PENTEST.md 6.1).
        user_content: Contenido del usuario (los datos a redactar). Nunca se mezcla
            con el system prompt: va en el turno `user` del mensaje.
        max_tokens: Tope de tokens de la respuesta del modelo.

    Returns:
        El texto generado por el modelo.

    Raises:
        AppError: code 'CLAUDE_UNAVAILABLE' (503) ante cualquier fallo de la API o
            si la respuesta no trae texto utilizable. No se filtra detalle interno.
    """
    try:
        response = await _client.messages.create(
            model=MODELO_CLAUDE,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception:
        logger.error("Fallo al invocar a Claude", extra={"modelo": MODELO_CLAUDE})
        raise AppError(
            "Servicio de generación no disponible", "CLAUDE_UNAVAILABLE", 503
        )

    texto = next((bloque.text for bloque in response.content if bloque.type == "text"), "")
    if not texto:
        logger.error("Respuesta de Claude sin texto", extra={"modelo": MODELO_CLAUDE})
        raise AppError(
            "Servicio de generación no disponible", "CLAUDE_UNAVAILABLE", 503
        )
    return texto
