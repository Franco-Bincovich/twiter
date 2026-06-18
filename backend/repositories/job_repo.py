"""Persistencia de jobs: interfaz abstracta + implementación en memoria.

InMemoryJobRepository es temporal. Al conectar Supabase se implementará
SupabaseJobRepository con la misma interfaz, sin tocar service ni controller.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from schemas.job import Job, JobStatus
from utils.errors import AppError


class JobRepository(ABC):
    """Interfaz de acceso a datos de jobs. Único punto de persistencia."""

    @abstractmethod
    async def create(self, cuit: str, razon_social: str | None) -> Job: ...

    @abstractmethod
    async def find_by_id(self, job_id: UUID) -> Job | None: ...

    @abstractmethod
    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        resultado: dict | None = None,
        error: dict | None = None,
    ) -> Job: ...


class InMemoryJobRepository(JobRepository):
    """Implementación en memoria, thread-safe con asyncio.Lock. Temporal."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, cuit: str, razon_social: str | None) -> Job:
        job = Job(cuit=cuit, razon_social=razon_social)
        async with self._lock:
            self._jobs[job.id] = job
        return job

    async def find_by_id(self, job_id: UUID) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        resultado: dict | None = None,
        error: dict | None = None,
    ) -> Job:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise AppError("Job no encontrado", "JOB_NOT_FOUND", 404)
            updated = job.model_copy(
                update={
                    "status": status,
                    "resultado": resultado,
                    "error": error,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._jobs[job_id] = updated
            return updated
