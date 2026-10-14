"""Request DTO for authoring a new Agent."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["CreateAgentRequest"]


class CreateAgentRequest(BaseModel):
    """Inputs for the bootstrap-agent transaction.

    Optional fields ride to the scaffolder only when given: bootstrap-agent
    owns the defaults (the permission mode per posture, the appearance vocabulary),
    so the studio never carries a second copy of them.
    """

    name: str
    title: str
    description: str
    refs: list[str]
    skills: list[str]
    doors: list[str] = []
    galaxy: str = "craft"
    permission: str | None = None
    writes: bool = False
    fresh_eyes: bool = False
    hair: str | None = None
    headwear: str | None = None
    eyes: str | None = None
    face: str | None = None
    #: Emails OWNERS will name as the new atom's owners.
    owners: list[str] = []
