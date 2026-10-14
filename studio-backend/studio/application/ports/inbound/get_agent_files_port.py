"""Inbound port: one agent, rendered for every harness, for a client-side install."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.rendered_agent import RenderedAgent

__all__ = ["GetAgentFilesPort"]


@runtime_checkable
class GetAgentFilesPort(Protocol):
    """Returns the agent files a client writes into its own runtime."""

    def execute(self, *, name: str, runtime: str | None = None) -> tuple[RenderedAgent, ...]: ...
