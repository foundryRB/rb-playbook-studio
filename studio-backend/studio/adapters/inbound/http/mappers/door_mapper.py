"""Mapper: domain DoorDoc to DoorResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.door_response import DoorResponse

if TYPE_CHECKING:
    from studio.domain.model.door_doc import DoorDoc

__all__ = ["map_door"]


def map_door(door: DoorDoc, *, can_edit: bool = False) -> DoorResponse:
    """Convert a declared door document to its response DTO."""
    return DoorResponse(
        name=door.name,
        kind=door.kind.value,
        galaxy=door.galaxy,
        refs=list(door.refs),
        summary=door.summary,
        raw=door.raw,
        can_edit=can_edit,
    )
