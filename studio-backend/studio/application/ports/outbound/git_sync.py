"""Outbound port: git persistence for the playbook working clone."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.sync_status import SyncStatus

__all__ = ["GitSync"]


@runtime_checkable
class GitSync(Protocol):
    """Commit, publish, and reconcile the playbook checkout with its upstream.

    The composition root decides the implementation: a real adapter over a
    managed clone (deployed), or a no-op over a working tree the operator
    commits themselves (local run). Use cases call this port unconditionally.
    """

    def commit_all(self, *, message: str, author: Actor) -> None:
        """Record every pending change in the checkout as one commit by `author`.

        The author is whoever made the change; the clone's own identity (the
        service) stays the committer.
        """
        ...

    def pull(self) -> None:
        """Reconcile with upstream head; raise SyncConflictError on conflict."""
        ...

    def push(self) -> None:
        """Publish local commits; raise SyncRejectedError when upstream moved."""
        ...

    def status(self) -> SyncStatus:
        """Report unpushed commits and the diffstat publishing would send."""
        ...
