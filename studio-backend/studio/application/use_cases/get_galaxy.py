"""Use case: fetch one galaxy's routing document."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.galaxy_doc import GalaxyDoc
from studio.logging import get_logger

__all__ = ["GetGalaxy"]

logger = get_logger(__name__)


class GetGalaxy:
    """Returns a parsed GALAXY.md. Implements GetGalaxyPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self, *, name: str) -> GalaxyDoc:
        galaxy = self._repository.get_galaxy(name=name)
        logger.info("Galaxy fetched: %s (%d sections)", name, len(galaxy.sections))
        return galaxy
