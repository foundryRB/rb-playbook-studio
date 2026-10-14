"""Use case: fetch one REF in detail."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.ref_doc import RefDoc
from studio.logging import get_logger

__all__ = ["GetRef"]

logger = get_logger(__name__)


class GetRef:
    """Returns one parsed REF. Implements GetRefPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self, *, name: str) -> RefDoc:
        """Return the REF with the given name, or raise EntityNotFoundError."""
        logger.debug("Fetching REF %s", name)
        return self._repository.get_ref(name=name)
