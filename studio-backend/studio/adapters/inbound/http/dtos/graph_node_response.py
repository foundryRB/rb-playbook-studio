"""Response DTO for one graph node."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["GraphNodeResponse"]


class GraphNodeResponse(BaseModel):
    """A playbook graph node returned over HTTP."""

    id: str
    kind: str
    label: str
    domain: str | None
    summary: str
    galaxy: str | None = None
    moons: list[str] = []
    fresh_eyes: bool | None = None
