"""Outbound port: the playbook's own renderings of an agent definition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.application.ports.outbound.skill_home_info import SkillHomeInfo

__all__ = ["AgentRenderer", "AgentRuntimeInfo"]


@runtime_checkable
class AgentRuntimeInfo(Protocol):
    """One harness the corpus can render for: its name, where it reads agents, and
    the installer option that overrides that directory."""

    @property
    def name(self) -> str: ...

    @property
    def install_hint(self) -> str: ...

    @property
    def dest(self) -> str: ...

    @property
    def suffix(self) -> str: ...

    @property
    def skills(self) -> SkillHomeInfo: ...


@runtime_checkable
class AgentRenderer(Protocol):
    """Renders a corpus agent file into a harness's own agent shape.

    The studio never spells a runtime's fields itself: it asks the playbook,
    whose installer owns every rendering, so no agent's shape is described in
    two places.
    """

    def runtimes(self) -> tuple[AgentRuntimeInfo, ...]: ...

    def render(self, *, raw: str, runtime: str) -> str: ...

    def installer_source(self) -> bytes:
        """The installer file itself, shipped to clients that apply a bundle with it."""
        ...
