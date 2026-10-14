"""Inbound port: replace a whole agent document behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateAgentDocumentPort"]


@runtime_checkable
class UpdateAgentDocumentPort(Protocol):
    """Gated whole-document agent editing."""

    def execute(self, *, actor: Actor | None, name: str, raw: str) -> ValidationReport: ...
