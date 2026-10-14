"""Outbound port: the playbook's deterministic validation gates."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.validation_report import ValidationReport

__all__ = ["PlaybookValidator"]


@runtime_checkable
class PlaybookValidator(Protocol):
    """Runs the intent-test suite and link checker against the playbook."""

    def validate(self) -> ValidationReport: ...
