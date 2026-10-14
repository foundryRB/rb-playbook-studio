"""Inbound port: reconcile the working clone with upstream head."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.sync_status import SyncStatus

__all__ = ["RefreshContentPort"]


@runtime_checkable
class RefreshContentPort(Protocol):
    """Pulls upstream head into the working clone and reports the sync state."""

    def execute(self, *, actor: Actor | None) -> SyncStatus: ...
