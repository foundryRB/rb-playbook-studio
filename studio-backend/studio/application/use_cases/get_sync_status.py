"""Use case: report the working clone's sync state."""

from __future__ import annotations

from studio.application.ports.outbound.git_sync import GitSync
from studio.domain.model.sync_status import SyncStatus

__all__ = ["GetSyncStatus"]


class GetSyncStatus:
    """Implements GetSyncStatusPort."""

    def __init__(self, git: GitSync) -> None:
        self._git = git

    def execute(self) -> SyncStatus:
        return self._git.status()
