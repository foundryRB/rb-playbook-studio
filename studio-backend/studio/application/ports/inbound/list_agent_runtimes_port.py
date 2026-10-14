"""Inbound port: the harnesses the playbook renders agents for."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.agent_runtime import AgentRuntime

__all__ = ["ListAgentRuntimesPort"]


@runtime_checkable
class ListAgentRuntimesPort(Protocol):
    """Returns every harness and its install hints from the playbook installer."""

    def execute(self) -> tuple[AgentRuntime, ...]:
        """Every harness with its declared skills and agents installation hints."""
        ...
