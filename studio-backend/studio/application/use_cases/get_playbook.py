"""Use case: fetch the playbook entry-point document."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.playbook_doc import PlaybookDoc
from studio.logging import get_logger

__all__ = ["GetPlaybook"]

logger = get_logger(__name__)


class GetPlaybook:
    """Returns the parsed AI-PLAYBOOK.md. Implements GetPlaybookPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self) -> PlaybookDoc:
        """Return the playbook document with its titled sections."""
        doc = self._repository.get_playbook()
        logger.debug("Playbook parsed into %d sections", len(doc.sections))
        return doc
