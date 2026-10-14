"""Inbound port: run the playbook validation gates on demand."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["RunValidationPort"]


@runtime_checkable
class RunValidationPort(Protocol):
    """Runs the intent tests + link checker and reports the outcome."""

    def execute(self, *, actor: Actor | None) -> ValidationReport: ...
