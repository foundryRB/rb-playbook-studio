"""Door routes: an MCP or RAG card's document, gated editing, gated creation."""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.create_door_request import CreateDoorRequest
from studio.adapters.inbound.http.dtos.door_response import DoorResponse
from studio.adapters.inbound.http.dtos.update_document_request import UpdateDocumentRequest
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.door_mapper import map_door
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.domain.model.rights import Action

__all__ = ["router"]

router = APIRouter()


@router.post("/doors", response_model=DoorResponse, status_code=201)
def create_door(
    request: CreateDoorRequest, container: ContainerDep, actor: ActorDep
) -> DoorResponse:
    """File a new MCP or RAG card in a galaxy; gated like every edit."""
    door = container.create_door().execute(
        actor=actor,
        kind=request.kind,
        name=request.name,
        galaxy=request.galaxy,
        raw=request.raw,
        owners=request.owners,
    )
    return map_door(door, can_edit=container.rights().may(actor, Action.EDIT, door.path))


@router.get("/doors/{name}", response_model=DoorResponse)
def get_door(name: str, container: ContainerDep, actor: ActorDep) -> DoorResponse:
    """Return one declared door's document (purpose and doctrine)."""
    door = container.get_door().execute(name=name)
    return map_door(door, can_edit=container.rights().may(actor, Action.EDIT, door.path))


@router.put("/doors/{name}", response_model=ValidationReportResponse)
def update_door_document(
    name: str,
    request: UpdateDocumentRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Replace the whole card; the edit survives only if the gates pass."""
    report = container.update_door_document().execute(actor=actor, name=name, raw=request.raw)
    return map_validation_report(report)
