"""Persistencia de refresh tokens: interfaz abstracta + implementación en memoria.

Los refresh tokens se guardan SIEMPRE hasheados, nunca en texto plano
(SEGURIDAD-PENTEST.md sección 2.5). El repo solo conoce el hash. InMemory es
temporal; al conectar Supabase se implementa SupabaseRefreshTokenRepository.
"""

import asyncio
from abc import ABC, abstractmethod
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StoredRefreshToken(BaseModel):
    """Refresh token persistido: solo su hash, nunca el token en texto plano."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    token_hash: str


class RefreshTokenRepository(ABC):
    """Interfaz de acceso a refresh tokens. Único punto de persistencia."""

    @abstractmethod
    async def save(self, user_id: UUID, token_hash: str) -> None: ...

    @abstractmethod
    async def find_by_user(self, user_id: UUID) -> StoredRefreshToken | None: ...

    @abstractmethod
    async def delete(self, token_id: UUID) -> None: ...


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    """Implementación en memoria, thread-safe con asyncio.Lock. Un token por usuario."""

    def __init__(self) -> None:
        self._by_user: dict[UUID, StoredRefreshToken] = {}
        self._lock = asyncio.Lock()

    async def save(self, user_id: UUID, token_hash: str) -> None:
        stored = StoredRefreshToken(user_id=user_id, token_hash=token_hash)
        async with self._lock:
            self._by_user[user_id] = stored

    async def find_by_user(self, user_id: UUID) -> StoredRefreshToken | None:
        async with self._lock:
            return self._by_user.get(user_id)

    async def delete(self, token_id: UUID) -> None:
        async with self._lock:
            for user_id, stored in self._by_user.items():
                if stored.id == token_id:
                    del self._by_user[user_id]
                    return
