"""Inbound port: fetch one declared door's document."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.door_doc import DoorDoc

__all__ = ["GetDoorPort"]


@runtime_checkable
class GetDoorPort(Protocol):
    """Returns a galaxy's mcps/<name>.md or rags/<name>.md, parsed."""

    def execute(self, *, name: str) -> DoorDoc: ...
