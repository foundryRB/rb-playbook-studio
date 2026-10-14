"""Inbound port: list the playbook's intent claims."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.intent_claim import IntentClaim

__all__ = ["ListClaimsPort"]


@runtime_checkable
class ListClaimsPort(Protocol):
    """Returns every claim declared in intent.yaml."""

    def execute(self) -> list[IntentClaim]: ...
