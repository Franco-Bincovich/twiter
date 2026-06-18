"""Validación y clasificación de CUIT argentino (lógica pura, sin DB ni HTTP).

El CUIT tiene formato XX-XXXXXXXX-X (11 dígitos). Los dos primeros dígitos son el
prefijo que indica el tipo de persona. Este módulo es el guardrail del producto:
solo deja pasar CUIT de personas jurídicas correctamente formados.
"""

import re

from utils.errors import AppError

_DIGITOS_CUIT = 11
_MULTIPLICADORES = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
_PREFIJOS_JURIDICA = {"30", "33", "34"}
_PREFIJOS_FISICA = {"20", "23", "24", "27"}


def limpiar_cuit(cuit: str) -> str:
    """Normaliza un CUIT dejando solo sus 11 dígitos.

    Args:
        cuit: CUIT en cualquier formato; puede incluir guiones, espacios y puntos.

    Returns:
        Los 11 dígitos del CUIT, sin separadores.

    Raises:
        AppError: code 'INVALID_CUIT' (400) si no quedan exactamente 11 dígitos
            numéricos tras remover los separadores.
    """
    solo_digitos = re.sub(r"[\s.\-]", "", cuit)
    if not solo_digitos.isdigit() or len(solo_digitos) != _DIGITOS_CUIT:
        raise AppError("CUIT inválido", "INVALID_CUIT", 400)
    return solo_digitos


def validar_digito_verificador(cuit: str) -> bool:
    """Valida el dígito verificador del CUIT con el algoritmo módulo 11.

    Args:
        cuit: CUIT ya limpio (11 dígitos numéricos).

    Returns:
        True si el dígito verificador coincide con el cálculo; False en caso
        contrario (incluido el caso en que el cálculo da 10, que invalida el CUIT).
    """
    suma = sum(int(digito) * mult for digito, mult in zip(cuit, _MULTIPLICADORES))
    verificador = 11 - (suma % 11)
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        return False
    return verificador == int(cuit[10])


def detectar_tipo_persona(cuit: str) -> str:
    """Determina el tipo de persona según el prefijo del CUIT.

    Args:
        cuit: CUIT ya limpio (11 dígitos numéricos).

    Returns:
        'juridica' o 'fisica' según los dos primeros dígitos.

    Raises:
        AppError: code 'UNKNOWN_CUIT_PREFIX' (400) si el prefijo no se reconoce.
    """
    prefijo = cuit[:2]
    if prefijo in _PREFIJOS_JURIDICA:
        return "juridica"
    if prefijo in _PREFIJOS_FISICA:
        return "fisica"
    raise AppError("Prefijo de CUIT no reconocido", "UNKNOWN_CUIT_PREFIX", 400)


def validar_cuit_juridica(cuit: str) -> str:
    """Valida que un CUIT corresponda a una persona jurídica bien formada.

    Guardrail del producto: única vía autorizada para que un CUIT entre al sistema.
    Orquesta la limpieza, la validación del dígito verificador y la clasificación
    del tipo de persona.

    Args:
        cuit: CUIT en cualquier formato (con o sin separadores).

    Returns:
        El CUIT limpio (11 dígitos) cuando corresponde a una persona jurídica válida.

    Raises:
        AppError: code 'INVALID_CUIT' (400) si el formato o el dígito verificador
            son inválidos.
        AppError: code 'UNKNOWN_CUIT_PREFIX' (400) si el prefijo no se reconoce.
        AppError: code 'PERSONA_FISICA_NOT_ALLOWED' (422) si el CUIT es de una
            persona física.
    """
    cuit_limpio = limpiar_cuit(cuit)
    if not validar_digito_verificador(cuit_limpio):
        raise AppError("CUIT inválido", "INVALID_CUIT", 400)
    if detectar_tipo_persona(cuit_limpio) == "fisica":
        raise AppError(
            "El producto solo procesa personas jurídicas",
            "PERSONA_FISICA_NOT_ALLOWED",
            422,
        )
    return cuit_limpio
