"""Inbound port: fetch the playbook reference graph."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.playbook_graph import PlaybookGraph

__all__ = ["GetGraphPort"]


@runtime_checkable
class GetGraphPort(Protocol):
    """Assembles the full node/edge graph of the playbook."""

    def execute(self) -> PlaybookGraph: ...
