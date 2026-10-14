"""Response DTO for one declared door's document."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["DoorResponse"]


class DoorResponse(BaseModel):
    """A declared door (mcps/<name>.md or rags/<name>.md) returned over HTTP."""

    name: str
    kind: str
    galaxy: str
    refs: list[str]
    summary: str
    raw: str
    #: Whether the reader may change this document (OWNERS); controls render from it.
    can_edit: bool
