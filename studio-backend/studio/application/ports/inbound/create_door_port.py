"""Inbound port: declare a new MCP or RAG card behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.door_doc import DoorDoc

__all__ = ["CreateDoorPort"]


@runtime_checkable
class CreateDoorPort(Protocol):
    """Files a card in a galaxy; removes it and raises if the gates fail."""

    def execute(
        self,
        *,
        actor: Actor | None,
        kind: str,
        name: str,
        galaxy: str,
        raw: str,
        owners: list[str] | None = None,
    ) -> DoorDoc: ...
