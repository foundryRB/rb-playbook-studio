"""Response DTO for one intent claim."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["IntentClaimResponse"]


class IntentClaimResponse(BaseModel):
    """An intent.yaml claim returned over HTTP."""

    claim_id: str
    statement: str
    rationale: str
    criticality: str
    status: str
