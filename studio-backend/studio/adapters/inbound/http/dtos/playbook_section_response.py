"""Response DTO for one playbook section."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["PlaybookSectionResponse"]


class PlaybookSectionResponse(BaseModel):
    """A titled AI-PLAYBOOK.md section returned over HTTP."""

    title: str
    body: str
