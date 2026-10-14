"""Inbound port: replace AI-PLAYBOOK.md behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdatePlaybookDocumentPort"]


@runtime_checkable
class UpdatePlaybookDocumentPort(Protocol):
    """Writes the full playbook document; rolls back and raises if gates fail."""

    def execute(self, *, actor: Actor | None, raw: str) -> ValidationReport: ...
