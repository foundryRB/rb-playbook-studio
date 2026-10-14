"""Inbound port: replace an MCP or RAG card behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.validation_report import ValidationReport

__all__ = ["UpdateDoorDocumentPort"]


@runtime_checkable
class UpdateDoorDocumentPort(Protocol):
    """Writes the full card; rolls back and raises if the gates fail."""

    def execute(self, *, actor: Actor | None, name: str, raw: str) -> ValidationReport: ...
