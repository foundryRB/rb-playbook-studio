"""Response DTO for one skill file."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["SkillFileResponse"]


class SkillFileResponse(BaseModel):
    """A text file from a skill folder returned over HTTP."""

    path: str
    content: str
