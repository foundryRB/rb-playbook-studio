"""Inbound port: list every nebula's roster summary."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.nebula_summary import NebulaSummary

__all__ = ["ListNebulaePort"]


@runtime_checkable
class ListNebulaePort(Protocol):
    """Returns one summary per nebulae/<territory>/ folder (HTTP surface only)."""

    def execute(self) -> list[NebulaSummary]: ...
