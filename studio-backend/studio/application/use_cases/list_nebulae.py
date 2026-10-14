"""Use case: list the unearned zone's nebulae."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.nebula_summary import NebulaSummary
from studio.logging import get_logger

__all__ = ["ListNebulae"]

logger = get_logger(__name__)


class ListNebulae:
    """Returns every nebula's roster summary. Implements ListNebulaePort.

    Wired to the HTTP adapter only: the quarantine (REF-Forge) keeps nebula
    content off the MCP door and out of the reference graph.
    """

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self) -> list[NebulaSummary]:
        nebulae = self._repository.list_nebulae()
        logger.info("Nebulae listed: %d territories", len(nebulae))
        return nebulae
