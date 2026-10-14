"""Request DTO for authoring a new REF."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["CreateRefRequest"]


class CreateRefRequest(BaseModel):
    """Inputs for a template-conformant new REF."""

    name: str
    domain: str
    title: str
    summary: str
    galaxy: str = "craft"
