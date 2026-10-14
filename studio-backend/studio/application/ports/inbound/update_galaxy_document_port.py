"""Inbound port: replace one galaxy's GALAXY.md behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateGalaxyDocumentPort"]


@runtime_checkable
class UpdateGalaxyDocumentPort(Protocol):
    """Writes the full galaxy document; rolls back and raises if gates fail."""

    def execute(self, *, actor: Actor | None, name: str, raw: str) -> ValidationReport: ...
