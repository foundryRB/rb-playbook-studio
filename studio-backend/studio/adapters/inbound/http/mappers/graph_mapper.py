"""Mapper: domain PlaybookGraph to GraphResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.graph_node_response import GraphNodeResponse
from studio.adapters.inbound.http.dtos.graph_response import GraphResponse
from studio.adapters.inbound.http.dtos.reference_edge_response import ReferenceEdgeResponse

if TYPE_CHECKING:
    from studio.domain.model.playbook_graph import PlaybookGraph

__all__ = ["map_graph"]


def map_graph(graph: PlaybookGraph) -> GraphResponse:
    """Convert the domain graph to its response DTO."""
    return GraphResponse(
        nodes=[
            GraphNodeResponse(
                id=n.id,
                kind=str(n.kind),
                label=n.label,
                domain=str(n.domain) if n.domain is not None else None,
                summary=n.summary,
                galaxy=n.galaxy,
                moons=list(n.moons),
                fresh_eyes=n.fresh_eyes,
            )
            for n in graph.nodes
        ],
        edges=[
            ReferenceEdgeResponse(source=e.source, target=e.target, kind=str(e.kind))
            for e in graph.edges
        ],
    )
