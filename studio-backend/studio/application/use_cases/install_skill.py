"""Use case: install a skill into the Claude runtime's skills directory."""

from __future__ import annotations

from studio.application.ports.outbound.skill_runtime import SkillRuntime
from studio.domain.model.skill_status import SkillStatus
from studio.logging import get_logger

__all__ = ["InstallSkill"]

logger = get_logger(__name__)


class InstallSkill:
    """Copies the master skill folder into the runtime. Implements InstallSkillPort."""

    def __init__(self, runtime: SkillRuntime) -> None:
        self._runtime = runtime

    def execute(self, *, name: str) -> SkillStatus:
        """Install (or reinstall) the skill and return its runtime state."""
        logger.info("Installing skill %s to the runtime", name)
        return self._runtime.install(name=name)
