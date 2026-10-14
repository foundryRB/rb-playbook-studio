"""Use case: fetch one Agent in detail."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.agent_doc import AgentDoc
from studio.logging import get_logger

__all__ = ["GetAgent"]

logger = get_logger(__name__)


class GetAgent:
    """Returns one parsed Agent. Implements GetAgentPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self, *, name: str) -> AgentDoc:
        """Return the agent with the given name, or raise EntityNotFoundError."""
        logger.debug("Fetching agent %s", name)
        return self._repository.get_agent(name=name)
