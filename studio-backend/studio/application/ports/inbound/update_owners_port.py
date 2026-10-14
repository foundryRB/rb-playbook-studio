"""Inbound port: replace the corpus's OWNERS file."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateOwnersPort"]


@runtime_checkable
class UpdateOwnersPort(Protocol):
    """Refuses OWNERS that does not parse or names a missing path; gates the rest."""

    def execute(self, *, actor: Actor | None, raw: str) -> ValidationReport: ...
