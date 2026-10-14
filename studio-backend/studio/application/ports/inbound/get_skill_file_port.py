"""Inbound port: read one file from a skill folder."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["GetSkillFilePort"]


@runtime_checkable
class GetSkillFilePort(Protocol):
    """Returns the bytes of one skill file."""

    def execute(self, *, name: str, rel_path: str) -> bytes: ...
