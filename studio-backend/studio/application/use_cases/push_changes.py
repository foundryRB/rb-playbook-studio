"""Use case: deliberately publish accumulated commits upstream."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import CHANGES_PUSHED, state_fact
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.domain.exceptions.sync_rejected_error import SyncRejectedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.sync_status import SyncStatus
from studio.logging import get_logger

__all__ = ["PushChanges"]

logger = get_logger(__name__)


class PushChanges:
    """Implements PushChangesPort. An admin's act; the service is the pusher.

    A rejected push means upstream moved: reconcile once (pull with rebase)
    and retry. A real conflict propagates raw from the pull; a second
    rejection propagates as-is rather than looping.
    """

    def __init__(
        self, git: GitSync, guard: CorpusGuard, events: EventPublisher | None = None
    ) -> None:
        self._git = git
        self._guard = guard
        self._events = events

    def execute(self, *, actor: Actor | None) -> SyncStatus:
        with self._guard.write(actor, Action.ADMINISTER):
            try:
                self._git.push()
            except SyncRejectedError:
                logger.info("Push rejected; reconciling with upstream and retrying")
                self._git.pull()
                self._git.push()
            logger.info("Push published local commits")
            status = self._git.status()
        # The push has landed before the fact is stated; the repo slug is the
        # pointer a reader fetches the commits from.
        state_fact(
            self._events,
            event_type=CHANGES_PUSHED,
            subject=status.repo or "playbook",
            data={"repo": status.repo},
        )
        return status
