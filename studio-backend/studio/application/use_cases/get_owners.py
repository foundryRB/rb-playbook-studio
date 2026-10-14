"""Use case: read OWNERS as the corpus holds it."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository

__all__ = ["GetOwners"]


class GetOwners:
    """Returns the OWNERS text, or None when the playbook has none. Implements GetOwnersPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self) -> str | None:
        return self._repository.read_owners()
