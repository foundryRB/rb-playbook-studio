"""Use case: fetch one declared door's document."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.model.door_doc import DoorDoc
from studio.logging import get_logger

__all__ = ["GetDoor"]

logger = get_logger(__name__)


class GetDoor:
    """Returns one declared door. Implements GetDoorPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self, *, name: str) -> DoorDoc:
        for door in self._repository.list_doors():
            if door.name == name:
                logger.info("Door fetched: %s (%s)", name, door.galaxy)
                return door
        raise EntityNotFoundError("Door", name)
