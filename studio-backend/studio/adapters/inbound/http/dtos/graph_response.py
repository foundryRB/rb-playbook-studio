"""Response DTO for the playbook graph."""

from __future__ import annotations

from pydantic import BaseModel

from studio.adapters.inbound.http.dtos.graph_node_response import GraphNodeResponse
from studio.adapters.inbound.http.dtos.reference_edge_response import ReferenceEdgeResponse

__all__ = ["GraphResponse"]


class GraphResponse(BaseModel):
    """The full playbook node/edge graph returned over HTTP."""

    nodes: list[GraphNodeResponse]
    edges: list[ReferenceEdgeResponse]
