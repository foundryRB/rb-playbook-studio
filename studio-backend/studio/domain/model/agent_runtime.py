"""A harness's installation metadata, supplied by the playbook installer."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["AgentRuntime"]


@dataclass(frozen=True)
class AgentRuntime:
    """Where a client writes one harness's skills and rendered agents."""

    name: str
    install_hint: str
    skills_install_hint: str
