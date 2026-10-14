"""Inbound port: edit one skill file behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateSkillFilePort"]


@runtime_checkable
class UpdateSkillFilePort(Protocol):
    """Writes one skill file; rolls back and raises if validation fails."""

    def execute(
        self, *, actor: Actor | None, name: str, rel_path: str, content: str
    ) -> ValidationReport: ...
