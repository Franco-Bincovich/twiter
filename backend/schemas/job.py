"""Schemas Pydantic de los jobs de consulta de CUIT (frontera de entrada/salida)."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    """Estados posibles de un job a lo largo de su ciclo de vida."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class JobCreateRequest(BaseModel):
    """Payload de creación de una consulta."""

    cuit: str = Field(min_length=1, max_length=20)
    razon_social: str | None = Field(default=None, max_length=200)


class Job(BaseModel):
    """Entidad de dominio del job, tal como se persiste y circula entre capas."""

    id: UUID = Field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    cuit: str
    razon_social: str | None = None
    resultado: dict | None = None
    error: dict | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobResponse(BaseModel):
    """Vista de salida del job para el cliente (polling del estado)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: JobStatus
    cuit: str
    razon_social: str | None
    resultado: dict | None
    error: dict | None
    created_at: datetime
    updated_at: datetime
