"""Response DTO for one REF section."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["RefSectionResponse"]


class RefSectionResponse(BaseModel):
    """A numbered REF section returned over HTTP."""

    number: int
    title: str
    body: str
    generated: bool
