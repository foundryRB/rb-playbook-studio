"""Use case: list every Agent on the roster."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.agent_doc import AgentDoc
from studio.logging import get_logger

__all__ = ["ListAgents"]

logger = get_logger(__name__)


class ListAgents:
    """Returns every parsed Agent. Implements ListAgentsPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self) -> list[AgentDoc]:
        """Return every agent, sorted by name."""
        agents = self._repository.list_agents()
        logger.debug("Listed %d agents", len(agents))
        return agents
