"""Use case: pull upstream head into the working clone."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.ports.outbound.git_sync import GitSync
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.sync_status import SyncStatus
from studio.logging import get_logger

__all__ = ["RefreshContent"]

logger = get_logger(__name__)


class RefreshContent:
    """Implements RefreshContentPort. An admin's act, and the poll's as the service."""

    def __init__(self, git: GitSync, guard: CorpusGuard) -> None:
        self._git = git
        self._guard = guard

    def execute(self, *, actor: Actor | None) -> SyncStatus:
        with self._guard.write(actor, Action.ADMINISTER):
            self._git.pull()
            logger.info("Content refreshed from upstream")
            return self._git.status()
