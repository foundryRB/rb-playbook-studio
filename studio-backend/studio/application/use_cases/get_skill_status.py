"""Use case: report a skill's runtime installation state."""

from __future__ import annotations

from studio.application.ports.outbound.skill_runtime import SkillRuntime
from studio.domain.model.skill_status import SkillStatus
from studio.logging import get_logger

__all__ = ["GetSkillStatus"]

logger = get_logger(__name__)


class GetSkillStatus:
    """Compares master vs runtime copy. Implements GetSkillStatusPort."""

    def __init__(self, runtime: SkillRuntime) -> None:
        self._runtime = runtime

    def execute(self, *, name: str) -> SkillStatus:
        """Return installed / in-sync state for the skill."""
        status = self._runtime.status(name=name)
        logger.debug("Skill %s: installed=%s in_sync=%s", name, status.installed, status.in_sync)
        return status
