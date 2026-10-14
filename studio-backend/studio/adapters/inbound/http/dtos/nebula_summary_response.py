"""Response DTO for one nebula's roster summary."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["NebulaSummaryResponse"]


class NebulaSummaryResponse(BaseModel):
    """One territory under study: subject line and stardust status counts."""

    territory: str
    subject: str
    note_count: int
    unsmelted: int
    taken: int
    burned: int
