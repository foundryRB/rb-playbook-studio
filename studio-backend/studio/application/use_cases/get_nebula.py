"""Use case: fetch one nebula's stardust."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.nebula_doc import NebulaDoc
from studio.logging import get_logger

__all__ = ["GetNebula"]

logger = get_logger(__name__)


class GetNebula:
    """Returns one territory's NEBULA.md and notes. Implements GetNebulaPort.

    Wired to the HTTP adapter only: the quarantine (REF-Forge) keeps nebula
    content off the MCP door and out of the reference graph.
    """

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self, *, territory: str) -> NebulaDoc:
        nebula = self._repository.get_nebula(territory=territory)
        logger.info("Nebula fetched: %s (%d notes)", territory, len(nebula.notes))
        return nebula
