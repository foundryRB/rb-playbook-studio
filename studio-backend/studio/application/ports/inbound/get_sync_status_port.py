"""Inbound port: report the working clone's state relative to upstream."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.sync_status import SyncStatus

__all__ = ["GetSyncStatusPort"]


@runtime_checkable
class GetSyncStatusPort(Protocol):
    """Reports unpushed commits and the diffstat a push would publish."""

    def execute(self) -> SyncStatus: ...
