"""Response DTO for the health check."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["HealthResponse"]


class HealthResponse(BaseModel):
    """Service liveness, version, and wired capabilities."""

    status: str
    version: str
    sync: bool
