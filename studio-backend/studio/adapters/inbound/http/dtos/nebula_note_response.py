"""Response DTO for one stardust note."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["NebulaNoteResponse"]


class NebulaNoteResponse(BaseModel):
    """A typed research note (REF-Forge stardust schema) returned over HTTP."""

    name: str
    type: str
    confidence: str
    vote: str | None
    seats: list[str]
    sources: list[str]
    links: list[str]
    status: str
    body: str
