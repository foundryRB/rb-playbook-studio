"""REF routes: detail, gated section and document editing, gated creation.

Plain (sync) handlers: FastAPI runs them on worker threads, so a write's
validation never holds the event loop and the health check keeps answering.
"""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.create_ref_request import CreateRefRequest
from studio.adapters.inbound.http.dtos.ref_detail_response import RefDetailResponse
from studio.adapters.inbound.http.dtos.update_document_request import UpdateDocumentRequest
from studio.adapters.inbound.http.dtos.update_section_request import UpdateSectionRequest
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.ref_mapper import map_ref
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.domain.model.rights import Action

__all__ = ["router"]

router = APIRouter()


@router.post("/refs", response_model=RefDetailResponse, status_code=201)
def create_ref(
    request: CreateRefRequest, container: ContainerDep, actor: ActorDep
) -> RefDetailResponse:
    """Author a new REF from the canonical template; gated like every edit."""
    ref = container.create_ref().execute(
        actor=actor,
        name=request.name,
        domain=request.domain,
        title=request.title,
        summary=request.summary,
        galaxy=request.galaxy,
    )
    return map_ref(ref, can_edit=container.rights().may(actor, Action.EDIT, ref.path))


@router.get("/refs/{name}", response_model=RefDetailResponse)
def get_ref(name: str, container: ContainerDep, actor: ActorDep) -> RefDetailResponse:
    """Return one parsed REF by name (e.g. REF-Python)."""
    ref = container.get_ref().execute(name=name)
    return map_ref(ref, can_edit=container.rights().may(actor, Action.EDIT, ref.path))


@router.put("/refs/{name}", response_model=ValidationReportResponse)
def update_ref_document(
    name: str,
    request: UpdateDocumentRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Replace the whole document; the edit survives only if the gates pass."""
    report = container.update_ref_document().execute(actor=actor, ref_name=name, raw=request.raw)
    return map_validation_report(report)


@router.put("/refs/{name}/sections/{number}", response_model=ValidationReportResponse)
def update_ref_section(
    name: str,
    number: int,
    request: UpdateSectionRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Write a section body; the edit survives only if the validation gates pass."""
    report = container.update_ref_section().execute(
        actor=actor, ref_name=name, number=number, body=request.body
    )
    return map_validation_report(report)
