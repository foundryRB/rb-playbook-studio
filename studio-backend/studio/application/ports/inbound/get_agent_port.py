"""Inbound port: fetch one Agent in detail."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.agent_doc import AgentDoc

__all__ = ["GetAgentPort"]


@runtime_checkable
class GetAgentPort(Protocol):
    """Returns one parsed Agent by name."""

    def execute(self, *, name: str) -> AgentDoc: ...
