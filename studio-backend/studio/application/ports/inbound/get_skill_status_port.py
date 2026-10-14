"""Inbound port: report a skill's runtime installation state."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.skill_status import SkillStatus

__all__ = ["GetSkillStatusPort"]


@runtime_checkable
class GetSkillStatusPort(Protocol):
    """Returns installed / in-sync state for a skill."""

    def execute(self, *, name: str) -> SkillStatus: ...
