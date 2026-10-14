"""Inbound port: replace a whole SKILL.md behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateSkillDocumentPort"]


@runtime_checkable
class UpdateSkillDocumentPort(Protocol):
    """Writes the full skill document; rolls back and raises if gates fail."""

    def execute(self, *, actor: Actor | None, name: str, raw: str) -> ValidationReport: ...
