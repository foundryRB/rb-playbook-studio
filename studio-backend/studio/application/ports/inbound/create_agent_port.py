"""Inbound port: author a new Agent behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.agent_doc import AgentDoc

__all__ = ["CreateAgentPort"]


@runtime_checkable
class CreateAgentPort(Protocol):
    """Runs the bootstrap-agent transaction; rolls it all back if gates fail."""

    def execute(
        self,
        *,
        actor: Actor | None,
        name: str,
        title: str,
        description: str,
        refs: list[str],
        skills: list[str],
        doors: list[str] | None = None,
        galaxy: str = "craft",
        permission: str | None = None,
        writes: bool = False,
        fresh_eyes: bool = False,
        hair: str | None = None,
        headwear: str | None = None,
        eyes: str | None = None,
        face: str | None = None,
        owners: list[str] | None = None,
    ) -> AgentDoc: ...
