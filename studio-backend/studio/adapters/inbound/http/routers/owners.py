"""OWNERS routes: the corpus's rights, read by anyone and replaced by an admin."""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.owners_response import OwnersResponse
from studio.adapters.inbound.http.dtos.update_document_request import UpdateDocumentRequest
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report

__all__ = ["router"]

router = APIRouter()


@router.get("/owners", response_model=OwnersResponse)
def get_owners(container: ContainerDep) -> OwnersResponse:
    """Return the OWNERS text, or null when the playbook has none."""
    return OwnersResponse(raw=container.get_owners().execute())


@router.put("/owners", response_model=ValidationReportResponse)
def update_owners(
    request: UpdateDocumentRequest, container: ContainerDep, actor: ActorDep
) -> ValidationReportResponse:
    """Replace OWNERS (admins). Refused when it does not parse or names a missing path."""
    report = container.update_owners().execute(actor=actor, raw=request.raw)
    return map_validation_report(report)
