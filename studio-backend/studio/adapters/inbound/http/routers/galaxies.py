"""Galaxy routes."""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.galaxy_response import GalaxyResponse
from studio.adapters.inbound.http.dtos.update_document_request import UpdateDocumentRequest
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.galaxy_mapper import map_galaxy
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.domain.model.rights import Action

__all__ = ["router"]

router = APIRouter()


@router.get("/galaxies/{name}", response_model=GalaxyResponse)
def get_galaxy(name: str, container: ContainerDep, actor: ActorDep) -> GalaxyResponse:
    """Return one galaxy's GALAXY.md parsed into titled sections."""
    galaxy = container.get_galaxy().execute(name=name)
    return map_galaxy(galaxy, can_edit=container.rights().may(actor, Action.EDIT, galaxy.path))


@router.put("/galaxies/{name}", response_model=ValidationReportResponse)
def update_galaxy(
    name: str,
    request: UpdateDocumentRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Replace one galaxy's GALAXY.md; the edit survives only if the gates pass."""
    report = container.update_galaxy_document().execute(actor=actor, name=name, raw=request.raw)
    return map_validation_report(report)
