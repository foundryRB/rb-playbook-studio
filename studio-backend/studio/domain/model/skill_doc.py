"""A Skill master document."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SkillDoc"]


@dataclass(frozen=True)
class SkillDoc:
    """A skills/<name>/SKILL.md, identified by its frontmatter `name`."""

    name: str
    description: str
    refs: tuple[str, ...]
    raw: str
    files: tuple[str, ...]
    galaxy: str | None = None
    #: The skill folder, relative to the playbook root.
    path: str = ""
