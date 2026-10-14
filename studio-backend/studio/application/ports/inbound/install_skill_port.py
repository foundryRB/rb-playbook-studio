"""Inbound port: install a skill into the runtime skills directory."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.skill_status import SkillStatus

__all__ = ["InstallSkillPort"]


@runtime_checkable
class InstallSkillPort(Protocol):
    """Installs (or reinstalls) the master skill folder into the runtime."""

    def execute(self, *, name: str) -> SkillStatus: ...
