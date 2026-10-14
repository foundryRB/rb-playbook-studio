"""Playbook document routes."""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.playbook_response import PlaybookResponse
from studio.adapters.inbound.http.dtos.update_document_request import UpdateDocumentRequest
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.playbook_mapper import map_playbook
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.application.use_cases.update_playbook_document import PLAYBOOK_PATH
from studio.domain.model.rights import Action

__all__ = ["router"]

router = APIRouter()


@router.get("/playbook", response_model=PlaybookResponse)
def get_playbook(container: ContainerDep, actor: ActorDep) -> PlaybookResponse:
    """Return AI-PLAYBOOK.md parsed into titled sections."""
    return map_playbook(
        container.get_playbook().execute(),
        can_edit=container.rights().may(actor, Action.EDIT, PLAYBOOK_PATH),
    )


@router.put("/playbook", response_model=ValidationReportResponse)
def update_playbook(
    request: UpdateDocumentRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Replace AI-PLAYBOOK.md; the edit survives only if the gates pass."""
    report = container.update_playbook_document().execute(actor=actor, raw=request.raw)
    return map_validation_report(report)
