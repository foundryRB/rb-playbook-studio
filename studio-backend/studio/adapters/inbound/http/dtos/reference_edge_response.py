"""Response DTO for one graph edge."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["ReferenceEdgeResponse"]


class ReferenceEdgeResponse(BaseModel):
    """A directed reference edge returned over HTTP."""

    source: str
    target: str
    kind: str
