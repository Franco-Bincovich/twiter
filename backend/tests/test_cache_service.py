"""Tests de la maquinaria de caché (services/cache_service.py).

Se usa asyncio.run para no depender de plugins async de pytest. La expiración se
prueba con un TTL muy corto y una espera real, sin tocar el reloj.
"""

import asyncio
import time

from services.cache_service import (
    construir_key,
    guardar_en_cache,
    obtener_cacheado,
)
from services.cache_service import cache_repo

FUENTE = "bcra"
CUIT = "30716595540"
VALUE = {"status": "ok", "deudas": []}


def test_set_get_devuelve_el_value_guardado():
    async def flujo():
        await guardar_en_cache(FUENTE, CUIT, VALUE, ttl_seconds=60)
        return await obtener_cacheado(FUENTE, CUIT)

    assert asyncio.run(flujo()) == VALUE


def test_get_de_key_inexistente_devuelve_none():
    assert asyncio.run(obtener_cacheado("arca", "33000000009")) is None


def test_get_de_entrada_expirada_devuelve_none():
    async def flujo():
        await guardar_en_cache(FUENTE, CUIT, VALUE, ttl_seconds=1)
        time.sleep(1.1)
        return await obtener_cacheado(FUENTE, CUIT)

    assert asyncio.run(flujo()) is None


def test_construir_key_arma_el_formato_fuente_cuit():
    assert construir_key("bcra", "30716595540") == "bcra:30716595540"


def test_delete_remueve_la_entrada():
    async def flujo():
        await guardar_en_cache(FUENTE, CUIT, VALUE, ttl_seconds=60)
        await cache_repo.delete(construir_key(FUENTE, CUIT))
        return await obtener_cacheado(FUENTE, CUIT)

    assert asyncio.run(flujo()) is None
