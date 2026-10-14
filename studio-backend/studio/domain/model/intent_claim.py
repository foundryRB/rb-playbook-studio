"""One claim from the playbook's intent.yaml."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["IntentClaim"]


@dataclass(frozen=True)
class IntentClaim:
    """A CSD intent claim (INT-XXX-NNN) with its governing metadata."""

    claim_id: str
    statement: str
    rationale: str
    criticality: str
    status: str
