"""Inbound port: list every Agent on the roster."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.agent_doc import AgentDoc

__all__ = ["ListAgentsPort"]


@runtime_checkable
class ListAgentsPort(Protocol):
    """Returns every parsed Agent."""

    def execute(self) -> list[AgentDoc]: ...
