"""Mapper: domain IntentClaim to IntentClaimResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.intent_claim_response import IntentClaimResponse

if TYPE_CHECKING:
    from studio.domain.model.intent_claim import IntentClaim

__all__ = ["map_claim"]


def map_claim(claim: IntentClaim) -> IntentClaimResponse:
    """Convert an intent claim to its response DTO."""
    return IntentClaimResponse(
        claim_id=claim.claim_id,
        statement=claim.statement,
        rationale=claim.rationale,
        criticality=claim.criticality,
        status=claim.status,
    )
