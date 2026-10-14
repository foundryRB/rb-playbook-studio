"""Request DTO for editing a REF section."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["UpdateSectionRequest"]


class UpdateSectionRequest(BaseModel):
    """The new markdown body for one REF section."""

    body: str
