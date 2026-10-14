"""Use case: list the harnesses and installation hints the playbook declares."""

from __future__ import annotations

from studio.application.ports.outbound.agent_renderer import AgentRenderer
from studio.domain.model.agent_runtime import AgentRuntime

__all__ = ["ListAgentRuntimes"]


class ListAgentRuntimes:
    """Returns harness metadata from the installer's own table. Implements
    ListAgentRuntimesPort.

    The set is the installer's, never the studio's: a harness exists here exactly
    when the playbook can render for it.
    """

    def __init__(self, renderer: AgentRenderer) -> None:
        self._renderer = renderer

    def execute(self) -> tuple[AgentRuntime, ...]:
        """Every harness and its install hints, in the installer's declared order."""
        return tuple(
            AgentRuntime(r.name, r.install_hint, r.skills.install_hint)
            for r in self._renderer.runtimes()
        )
