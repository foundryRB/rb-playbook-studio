"""Inbound port: fetch one nebula's full stardust."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.nebula_doc import NebulaDoc

__all__ = ["GetNebulaPort"]


@runtime_checkable
class GetNebulaPort(Protocol):
    """Returns one territory's NEBULA.md and parsed notes (HTTP surface only)."""

    def execute(self, *, territory: str) -> NebulaDoc: ...
