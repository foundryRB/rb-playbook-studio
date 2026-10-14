"""Outbound metadata contract: a harness's declared skills home."""

from __future__ import annotations

from typing import Protocol

__all__ = ["SkillHomeInfo"]


class SkillHomeInfo(Protocol):
    """The skills home declared by the playbook installer for a harness."""

    @property
    def install_hint(self) -> str: ...
