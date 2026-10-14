"""Response DTO for one nebula's full stardust."""

from __future__ import annotations

from pydantic import BaseModel

from studio.adapters.inbound.http.dtos.nebula_note_response import NebulaNoteResponse

__all__ = ["NebulaDetailResponse"]


class NebulaDetailResponse(BaseModel):
    """A nebula returned over HTTP: the fronting NEBULA.md plus every note.

    Served on the human surface only; the MCP door never carries nebula
    content (the quarantine, REF-Forge).
    """

    territory: str
    subject: str
    raw: str
    notes: list[NebulaNoteResponse]
