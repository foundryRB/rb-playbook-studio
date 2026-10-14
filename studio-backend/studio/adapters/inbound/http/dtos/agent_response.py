"""Response DTO for one Agent."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["AgentAppearanceResponse", "AgentPostureResponse", "AgentResponse"]


class AgentPostureResponse(BaseModel):
    """How the agent behaves at its runtime."""

    permission: str
    writes: bool
    fresh_eyes: bool


class AgentAppearanceResponse(BaseModel):
    """The agent's face on the human surfaces; absent for fresh-eyes agents."""

    hair: str
    headwear: str
    eyes: str
    face: str


class AgentResponse(BaseModel):
    """A parsed agents/<name>.md returned over HTTP."""

    name: str
    title: str
    description: str
    galaxy: str
    refs: list[str]
    skills: list[str]
    doors: list[str]
    posture: AgentPostureResponse
    appearance: AgentAppearanceResponse | None = None
    summary: str
    raw: str
    #: Whether the reader may change this document (OWNERS); controls render from it.
    can_edit: bool
    body: str
