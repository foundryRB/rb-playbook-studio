"""Nebula routes: the unearned zone, served to humans only.

These routes have no MCP mirror by design: the quarantine (REF-Forge) keeps
stardust off the machine door, and the reference graph never carries a nebula
node. The maps render nebulae dim beside the earned galaxies.
"""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ContainerDep
from studio.adapters.inbound.http.dtos.nebula_detail_response import NebulaDetailResponse
from studio.adapters.inbound.http.dtos.nebula_summary_response import NebulaSummaryResponse
from studio.adapters.inbound.http.mappers.nebula_mapper import map_nebula, map_nebula_summary

__all__ = ["router"]

router = APIRouter()


@router.get("/nebulae", response_model=list[NebulaSummaryResponse])
async def list_nebulae(container: ContainerDep) -> list[NebulaSummaryResponse]:
    """Return every nebula's roster summary (territory, subject, status counts)."""
    return [map_nebula_summary(n) for n in container.list_nebulae().execute()]


@router.get("/nebulae/{territory}", response_model=NebulaDetailResponse)
async def get_nebula(territory: str, container: ContainerDep) -> NebulaDetailResponse:
    """Return one nebula: NEBULA.md raw plus every note's frontmatter and body."""
    return map_nebula(container.get_nebula().execute(territory=territory))
