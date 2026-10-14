"""Response DTO for a skill's runtime state."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["SkillStatusResponse"]


class SkillStatusResponse(BaseModel):
    """Installed / in-sync state of a skill in the runtime directory."""

    installed: bool
    in_sync: bool
