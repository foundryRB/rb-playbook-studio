"""Response DTO for the corpus's OWNERS file."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["OwnersResponse"]


class OwnersResponse(BaseModel):
    """The OWNERS text, or null when the playbook has none (everyone reads)."""

    raw: str | None
