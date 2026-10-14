"""Mapper: domain SkillDoc to SkillResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.skill_response import SkillResponse

if TYPE_CHECKING:
    from studio.domain.model.skill_doc import SkillDoc
    from studio.domain.model.skill_status import SkillStatus

__all__ = ["body_of", "map_skill"]


def body_of(raw: str) -> str:
    """Markdown after the closing frontmatter fence."""
    if raw.startswith("---"):
        close = raw.find("\n---", 3)
        if close != -1:
            return raw[close + 4 :].lstrip("\n")
    return raw


def map_skill(skill: SkillDoc, status: SkillStatus, *, can_edit: bool = False) -> SkillResponse:
    """Convert a parsed skill and its runtime state to the response DTO."""
    return SkillResponse(
        name=skill.name,
        description=skill.description,
        refs=list(skill.refs),
        raw=skill.raw,
        body=body_of(skill.raw),
        files=list(skill.files),
        installed=status.installed,
        in_sync=status.in_sync,
        can_edit=can_edit,
        galaxy=skill.galaxy,
    )
