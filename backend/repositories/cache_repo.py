"""Caché con TTL: interfaz abstracta + implementación en memoria.

InMemoryCacheRepository es temporal. Al conectar Supabase se implementará
SupabaseCacheRepository con la misma interfaz, sin tocar service ni controller.

La expiración se mide con time.monotonic() (reloj monótono): inmune a cambios
del reloj del sistema, que falsearían el TTL hacia atrás o adelante.
"""

import asyncio
import time
from abc import ABC, abstractmethod


class CacheRepository(ABC):
    """Interfaz de caché con TTL. Único punto de almacenamiento de respuestas."""

    @abstractmethod
    async def get(self, key: str) -> dict | None:
        """Devuelve el value cacheado, o None si no existe o ya expiró."""
        ...

    @abstractmethod
    async def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        """Guarda value bajo key, válido por ttl_seconds segundos."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Elimina la entrada de key; no falla si no existe."""
        ...


class InMemoryCacheRepository(CacheRepository):
    """Implementación en memoria, thread-safe con asyncio.Lock. Temporal.

    Cada entrada se guarda como (value, expira_en), donde expira_en es un instante
    del reloj monótono. La expiración es lazy: get() limpia la entrada vencida.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[dict, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> dict | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expira_en = entry
            if time.monotonic() >= expira_en:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        async with self._lock:
            self._store[key] = (value, time.monotonic() + ttl_seconds)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)
