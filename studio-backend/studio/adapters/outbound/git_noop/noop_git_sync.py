"""GitSync for the local run: the operator owns the commits."""

from __future__ import annotations

from studio.domain.model.actor import Actor
from studio.domain.model.sync_status import SyncStatus
from studio.logging import get_logger

__all__ = ["NoopGitSync"]

logger = get_logger(__name__)


class NoopGitSync:
    """Implements GitSync over a working tree the studio does not manage.

    The local composition wires this so gated edits land in the sibling
    checkout's working tree and the operator commits with their own tools.
    """

    def commit_all(self, *, message: str, author: Actor) -> None:
        logger.debug("Local run: leaving edit by %s uncommitted (%s)", author.email, message)

    def pull(self) -> None:
        logger.debug("Local run: pull is operator-owned")

    def push(self) -> None:
        logger.debug("Local run: push is operator-owned")

    def status(self) -> SyncStatus:
        # No repo slug: this composition manages no clone, so it cannot name an
        # upstream. Reporting "" (unknown) is honest; a guess here would be the
        # exact stale literal the field exists to remove.
        return SyncStatus(unpushed_commits=0, diff_stat="", repo="")
