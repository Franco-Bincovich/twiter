"""Situación crediticia de una empresa según la Central de Deudores del BCRA.

Orquesta los tres endpoints del BCRA (deuda actual, histórico y cheques rechazados)
y delega la normalización en `services/bcra_normalizer`. Todo el transporte vive en
`integrations/bcra_client`; acá solo hay orquestación y tolerancia a fallos.

Diseño de tolerancia a fallos: la deuda actual es el núcleo del informe, así que si
ese endpoint cae el fallo se propaga. El histórico y los cheques son complementarios:
si caen, su sección queda con los defaults vacíos y el informe igual se arma.
"""

import asyncio

from integrations import bcra_client
from services import bcra_normalizer
from utils.logger import logger


async def obtener_situacion_crediticia(cuit: str) -> dict:
    """Consulta y normaliza la situación crediticia de un CUIT en el BCRA.

    Llama a los tres endpoints en paralelo. El de deuda actual es obligatorio: si
    falla, propaga el error. El histórico y los cheques son tolerantes: si fallan,
    su sección queda vacía sin tumbar el informe. Un 404 (sin datos) ya llega como
    None desde el cliente y también deja la sección con sus defaults.

    Args:
        cuit: CUIT de 11 dígitos sin guiones, ya validado por `cuit_service`.

    Returns:
        Dict con las claves 'denominacion', 'actual', 'historico' y 'cheques'.

    Raises:
        AppError: 'BCRA_INVALID_CUIT' (400) o 'BCRA_UNAVAILABLE' (503) si falla el
            endpoint de deuda actual (núcleo del informe).
    """
    deudas, historicas, cheques = await asyncio.gather(
        bcra_client.consultar_deudas(cuit),
        bcra_client.consultar_historicas(cuit),
        bcra_client.consultar_cheques(cuit),
        return_exceptions=True,
    )
    if isinstance(deudas, BaseException):
        raise deudas  # la deuda actual es el núcleo: su fallo tumba la consulta
    # Histórico y cheques son complementarios: si fallaron, se degradan a vacío.
    historicas = None if isinstance(historicas, BaseException) else historicas
    cheques = None if isinstance(cheques, BaseException) else cheques

    logger.info("Consulta BCRA realizada", extra={"cuit": cuit})
    return {
        "denominacion": bcra_normalizer.denominacion(deudas, historicas, cheques),
        "actual": bcra_normalizer.normalizar_actual(deudas),
        "historico": bcra_normalizer.normalizar_historico(historicas),
        "cheques": bcra_normalizer.normalizar_cheques(cheques),
    }
