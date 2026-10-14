"""Use case: fetch one Skill in detail."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.skill_doc import SkillDoc
from studio.logging import get_logger

__all__ = ["GetSkill"]

logger = get_logger(__name__)


class GetSkill:
    """Returns one parsed Skill. Implements GetSkillPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self, *, name: str) -> SkillDoc:
        """Return the skill with the given name, or raise EntityNotFoundError."""
        logger.debug("Fetching skill %s", name)
        return self._repository.get_skill(name=name)
