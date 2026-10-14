"""Inbound port: author a new Skill behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.skill_doc import SkillDoc

__all__ = ["CreateSkillPort"]


@runtime_checkable
class CreateSkillPort(Protocol):
    """Runs the bootstrap-skill transaction; rolls it all back if gates fail."""

    def execute(
        self,
        *,
        actor: Actor | None,
        name: str,
        description: str,
        refs: list[str],
        galaxy: str = "craft",
        owners: list[str] | None = None,
    ) -> SkillDoc: ...
