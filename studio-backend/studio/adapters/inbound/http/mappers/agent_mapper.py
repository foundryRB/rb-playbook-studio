"""Mapper: domain AgentDoc to AgentResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.agent_response import (
    AgentAppearanceResponse,
    AgentPostureResponse,
    AgentResponse,
)
from studio.adapters.inbound.http.mappers.skill_mapper import body_of

if TYPE_CHECKING:
    from studio.domain.model.agent_doc import AgentDoc

__all__ = ["map_agent"]


def map_agent(agent: AgentDoc, *, can_edit: bool = False) -> AgentResponse:
    """Convert a parsed agent to the response DTO."""
    return AgentResponse(
        name=agent.name,
        title=agent.title,
        description=agent.description,
        galaxy=agent.galaxy,
        refs=list(agent.refs),
        skills=list(agent.skills),
        doors=list(agent.doors),
        posture=AgentPostureResponse(
            permission=agent.posture.permission,
            writes=agent.posture.writes,
            fresh_eyes=agent.posture.fresh_eyes,
        ),
        appearance=(
            AgentAppearanceResponse(
                hair=agent.appearance.hair,
                headwear=agent.appearance.headwear,
                eyes=agent.appearance.eyes,
                face=agent.appearance.face,
            )
            if agent.appearance is not None
            else None
        ),
        summary=agent.summary,
        raw=agent.raw,
        can_edit=can_edit,
        body=body_of(agent.raw),
    )
