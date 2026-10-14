"""Inbound port: fetch one Skill in detail."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.skill_doc import SkillDoc

__all__ = ["GetSkillPort"]


@runtime_checkable
class GetSkillPort(Protocol):
    """Returns one parsed Skill by name."""

    def execute(self, *, name: str) -> SkillDoc: ...
