"""Use case: list the playbook's intent claims."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.intent_claim import IntentClaim
from studio.logging import get_logger

__all__ = ["ListClaims"]

logger = get_logger(__name__)


class ListClaims:
    """Returns every intent.yaml claim. Implements ListClaimsPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self) -> list[IntentClaim]:
        """Return all claims declared in the playbook's intent.yaml."""
        claims = self._repository.list_claims()
        logger.debug("Listing %d intent claims", len(claims))
        return claims
