"""Inbound port: edit one REF section behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateRefSectionPort"]


@runtime_checkable
class UpdateRefSectionPort(Protocol):
    """Writes a section body; rolls back and raises if validation fails."""

    def execute(
        self, *, actor: Actor | None, ref_name: str, number: int, body: str
    ) -> ValidationReport: ...
