"""Inbound port: replace a whole REF document behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateRefDocumentPort"]


@runtime_checkable
class UpdateRefDocumentPort(Protocol):
    """Writes the full document; rolls back and raises if validation fails."""

    def execute(self, *, actor: Actor | None, ref_name: str, raw: str) -> ValidationReport: ...
