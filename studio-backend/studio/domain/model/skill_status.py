"""Runtime installation state of a skill."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SkillStatus"]


@dataclass(frozen=True)
class SkillStatus:
    """Whether the skill is installed in the runtime dir and byte-identical."""

    installed: bool
    in_sync: bool
