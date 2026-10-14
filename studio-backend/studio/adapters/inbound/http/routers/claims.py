"""Intent-claim routes."""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ContainerDep
from studio.adapters.inbound.http.dtos.intent_claim_response import IntentClaimResponse
from studio.adapters.inbound.http.mappers.claim_mapper import map_claim

__all__ = ["router"]

router = APIRouter()


@router.get("/claims", response_model=list[IntentClaimResponse])
async def list_claims(container: ContainerDep) -> list[IntentClaimResponse]:
    """Return every claim in the playbook's intent.yaml."""
    return [map_claim(c) for c in container.list_claims().execute()]
