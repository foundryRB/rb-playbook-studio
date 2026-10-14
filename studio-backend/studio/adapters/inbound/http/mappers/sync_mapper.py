"""Map SyncStatus domain objects to response DTOs."""

from __future__ import annotations

from studio.adapters.inbound.http.dtos.sync_status_response import SyncStatusResponse
from studio.domain.model.sync_status import SyncStatus

__all__ = ["map_sync_status"]


def map_sync_status(status: SyncStatus) -> SyncStatusResponse:
    return SyncStatusResponse(
        unpushed_commits=status.unpushed_commits,
        diff_stat=status.diff_stat,
        repo=status.repo,
    )
