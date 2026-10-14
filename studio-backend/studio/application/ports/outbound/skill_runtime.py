"""Outbound port: the Claude runtime's installed-skills directory."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.skill_status import SkillStatus

__all__ = ["SkillRuntime"]


@runtime_checkable
class SkillRuntime(Protocol):
    """Installs playbook skills into the runtime and reports their state."""

    def status(self, *, name: str) -> SkillStatus: ...

    def install(self, *, name: str) -> SkillStatus: ...
