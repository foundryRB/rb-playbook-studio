"""Agent routes: roster, detail, gated editing, gated creation.

Plain (sync) handlers: FastAPI runs them on worker threads, so a write's
validation never holds the event loop and the health check keeps answering.
"""

from __future__ import annotations

from fastapi import APIRouter

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.agent_response import AgentResponse
from studio.adapters.inbound.http.dtos.create_agent_request import CreateAgentRequest
from studio.adapters.inbound.http.dtos.update_document_request import UpdateDocumentRequest
from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse
from studio.adapters.inbound.http.mappers.agent_mapper import map_agent
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.domain.model.rights import Action

__all__ = ["router"]

router = APIRouter()


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(container: ContainerDep, actor: ActorDep) -> list[AgentResponse]:
    """Return the whole agent roster, parsed."""
    rights = container.rights()
    return [
        map_agent(agent, can_edit=rights.may(actor, Action.EDIT, agent.path))
        for agent in container.list_agents().execute()
    ]


@router.post("/agents", response_model=AgentResponse, status_code=201)
def create_agent(
    request: CreateAgentRequest, container: ContainerDep, actor: ActorDep
) -> AgentResponse:
    """Run the bootstrap-agent transaction; gated like every edit."""
    agent = container.create_agent().execute(
        actor=actor,
        name=request.name,
        title=request.title,
        description=request.description,
        refs=request.refs,
        skills=request.skills,
        doors=request.doors,
        galaxy=request.galaxy,
        permission=request.permission,
        writes=request.writes,
        fresh_eyes=request.fresh_eyes,
        hair=request.hair,
        headwear=request.headwear,
        eyes=request.eyes,
        face=request.face,
        owners=request.owners,
    )
    return map_agent(agent, can_edit=container.rights().may(actor, Action.EDIT, agent.path))


@router.get("/agents/{name}", response_model=AgentResponse)
def get_agent(name: str, container: ContainerDep, actor: ActorDep) -> AgentResponse:
    """Return one parsed agent: identity, licence, doors, posture, appearance."""
    agent = container.get_agent().execute(name=name)
    return map_agent(agent, can_edit=container.rights().may(actor, Action.EDIT, agent.path))


@router.put("/agents/{name}", response_model=ValidationReportResponse)
def update_agent_document(
    name: str,
    request: UpdateDocumentRequest,
    container: ContainerDep,
    actor: ActorDep,
) -> ValidationReportResponse:
    """Replace the whole agent document; the edit survives only if the gates pass."""
    report = container.update_agent_document().execute(actor=actor, name=name, raw=request.raw)
    return map_validation_report(report)
