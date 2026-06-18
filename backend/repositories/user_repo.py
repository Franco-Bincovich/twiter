"""Persistencia de usuarios: interfaz abstracta + implementación en memoria.

InMemoryUserRepository es temporal. Al conectar Supabase se implementará
SupabaseUserRepository con la misma interfaz, sin tocar service ni controller.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from schemas.auth import User


class UserRepository(ABC):
    """Interfaz de acceso a datos de usuarios. Único punto de persistencia."""

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def create(self, email: str, password_hash: str) -> User: ...

    @abstractmethod
    async def update_last_login(self, user_id: UUID) -> None: ...

    @abstractmethod
    async def update_onboarding_completed(self, user_id: UUID) -> None: ...


class InMemoryUserRepository(UserRepository):
    """Implementación en memoria, thread-safe con asyncio.Lock. Temporal."""

    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        self._last_login: dict[UUID, datetime] = {}
        self._lock = asyncio.Lock()

    async def find_by_email(self, email: str) -> User | None:
        async with self._lock:
            for user in self._users.values():
                if user.email == email:
                    return user
            return None

    async def find_by_id(self, user_id: UUID) -> User | None:
        async with self._lock:
            return self._users.get(user_id)

    async def create(self, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        async with self._lock:
            self._users[user.id] = user
        return user

    async def update_last_login(self, user_id: UUID) -> None:
        async with self._lock:
            self._last_login[user_id] = datetime.now(timezone.utc)

    async def update_onboarding_completed(self, user_id: UUID) -> None:
        async with self._lock:
            user = self._users.get(user_id)
            if user is not None:
                self._users[user_id] = user.model_copy(
                    update={"onboarding_completed": True}
                )
