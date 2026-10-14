"""Graph route."""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ContainerDep
from studio.adapters.inbound.http.dtos.graph_response import GraphResponse
from studio.adapters.inbound.http.mappers.graph_mapper import map_graph

__all__ = ["router"]

router = APIRouter()


@router.get("/graph", response_model=GraphResponse)
async def get_graph(container: ContainerDep) -> GraphResponse:
    """Return the full playbook reference graph."""
    return map_graph(container.get_graph().execute())
