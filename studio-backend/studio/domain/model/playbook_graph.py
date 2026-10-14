"""The playbook reference graph."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.graph_node import GraphNode
from studio.domain.model.reference_edge import ReferenceEdge

__all__ = ["PlaybookGraph"]


@dataclass(frozen=True)
class PlaybookGraph:
    """All nodes and directed reference edges of the playbook."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[ReferenceEdge, ...]
