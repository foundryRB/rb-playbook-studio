"""Skill routes: detail, files, gated editing, gated creation, runtime install.

Plain (sync) handlers: FastAPI runs them on worker threads, so a write's
validation never holds the event loop and the health check keeps answering.
"""

from __future__ import annotations

import io

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.create_skill_request import CreateSkillRequest
from studio.adapters.inbound.http.dtos.skill_file_response import SkillFileResponse
from studio.adapters.inbound.http.dtos.skill_response import SkillResponse
from studio.adapters.inbound.http.dtos.skill_status_response import SkillStatusResponse
from studio.adapters.inbound.http.dtos.update_document_request import UpdateDocumentRequest
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.skill_mapper import map_skill
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.domain.exceptions.unsupported_capability_error import UnsupportedCapabilityError
from studio.domain.model.rights import Action

__all__ = ["router"]

router = APIRouter()


@router.post("/skills", response_model=SkillResponse, status_code=201)
def create_skill(
    request: CreateSkillRequest, container: ContainerDep, actor: ActorDep
) -> SkillResponse:
    """Run the bootstrap-skill transaction; gated like every edit."""
    skill = container.create_skill().execute(
        actor=actor,
        name=request.name,
        description=request.description,
        refs=request.refs,
        galaxy=request.galaxy,
        owners=request.owners,
    )
    status = container.get_skill_status().execute(name=skill.name)
    return map_skill(skill, status, can_edit=container.rights().may(actor, Action.EDIT, skill.path))


@router.get("/skills/{name}", response_model=SkillResponse)
def get_skill(name: str, container: ContainerDep, actor: ActorDep) -> SkillResponse:
    """Return one parsed skill, its file list, and its runtime state."""
    skill = container.get_skill().execute(name=name)
    status = container.get_skill_status().execute(name=name)
    return map_skill(skill, status, can_edit=container.rights().may(actor, Action.EDIT, skill.path))


@router.put("/skills/{name}", response_model=ValidationReportResponse)
def update_skill_document(
    name: str,
    request: UpdateDocumentRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Replace the whole SKILL.md; the edit survives only if the gates pass."""
    report = container.update_skill_document().execute(actor=actor, name=name, raw=request.raw)
    return map_validation_report(report)


@router.get("/skills/{name}/files/{rel_path:path}", response_model=SkillFileResponse)
def get_skill_file(name: str, rel_path: str, container: ContainerDep) -> SkillFileResponse:
    """Return one file from the skill folder as text for the reader: UTF-8 with
    undecodable bytes replaced and line endings read as newlines."""
    data = container.get_skill_file().execute(name=name, rel_path=rel_path)
    text = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace").read()
    return SkillFileResponse(path=rel_path, content=text)


@router.put("/skills/{name}/files/{rel_path:path}", response_model=ValidationReportResponse)
def update_skill_file(
    name: str,
    rel_path: str,
    request: UpdateDocumentRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Write one skill file; the edit survives only if the gates pass."""
    report = container.update_skill_file().execute(
        actor=actor, name=name, rel_path=rel_path, content=request.raw
    )
    return map_validation_report(report)


@router.post("/skills/{name}/install", response_model=SkillStatusResponse)
def install_skill(name: str, container: ContainerDep) -> SkillStatusResponse:
    """Copy the master skill folder into the Claude runtime's skills directory.

    Local-composition only: a managed-clone deployment has no skills runtime
    of its own; agents install skills on their machines via the MCP tools.
    """
    if not container.runtime_install_enabled:
        raise UnsupportedCapabilityError(
            "runtime install is local-only: this deployment has no skills runtime; "
            "connect an agent to /mcp and ask it to install the skill"
        )
    status = container.install_skill().execute(name=name)
    return SkillStatusResponse(installed=status.installed, in_sync=status.in_sync)
