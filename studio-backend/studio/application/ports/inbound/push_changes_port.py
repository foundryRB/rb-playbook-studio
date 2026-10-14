"""Inbound port: deliberately publish accumulated local commits."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.sync_status import SyncStatus

__all__ = ["PushChangesPort"]


@runtime_checkable
class PushChangesPort(Protocol):
    """Pushes local commits upstream and reports the resulting sync state."""

    def execute(self, *, actor: Actor | None) -> SyncStatus: ...
