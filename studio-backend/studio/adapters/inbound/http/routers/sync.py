"""Sync routes: status, deliberate push, and upstream refresh.

Mounted only when the composition manages the clone (deployed wiring); the
local run's working tree is operator-owned and has no sync surface. Push and
refresh are an admin's acts.

Every handler here drives a blocking `git` subprocess, so each is a plain
(sync) handler FastAPI runs on a worker thread rather than on the event loop.
A manual refresh or push otherwise freezes the single Uvicorn worker for the
length of the git operation (up to the 120 s subprocess timeout), stalling
health probes and every other request.
"""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.sync_status_response import SyncStatusResponse
from studio.adapters.inbound.http.mappers.sync_mapper import map_sync_status

__all__ = ["router"]

router = APIRouter()


@router.get("/sync/status", response_model=SyncStatusResponse)
def sync_status(container: ContainerDep) -> SyncStatusResponse:
    """Report unpushed commits and the diffstat a push would publish."""
    return map_sync_status(container.get_sync_status().execute())


@router.post("/sync/push", response_model=SyncStatusResponse)
def push_changes(container: ContainerDep, actor: ActorDep) -> SyncStatusResponse:
    """Publish accumulated local commits upstream (rebase-retry on rejection)."""
    return map_sync_status(container.push_changes().execute(actor=actor))


@router.post("/sync/refresh", response_model=SyncStatusResponse)
def refresh_content(container: ContainerDep, actor: ActorDep) -> SyncStatusResponse:
    """Pull upstream head into the working clone."""
    return map_sync_status(container.refresh_content().execute(actor=actor))
