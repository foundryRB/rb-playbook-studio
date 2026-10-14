"""A carried agent planet: a galaxies/<galaxy>/agents/<name>.md file."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["AgentAppearance", "AgentDoc", "AgentPosture"]


@dataclass(frozen=True)
class AgentPosture:
    """How an agent behaves at its runtime: permission mode, writes, fresh eyes."""

    permission: str
    writes: bool
    fresh_eyes: bool


@dataclass(frozen=True)
class AgentAppearance:
    """The agent's face on the human surfaces; absent for fresh-eyes agents."""

    hair: str
    headwear: str
    eyes: str
    face: str


@dataclass(frozen=True)
class AgentDoc:
    """Who does the work: identity, the description a harness routes on, the
    paragraph it runs under, licensed skills, needed doors.

    The file never carries procedure (its skills do) and never the binding
    (model, credential, endpoints belong to the environment) - REF-Universe §4.
    """

    name: str
    title: str
    description: str
    galaxy: str
    refs: tuple[str, ...]
    skills: tuple[str, ...]
    doors: tuple[str, ...]
    posture: AgentPosture
    appearance: AgentAppearance | None
    summary: str
    raw: str
    #: Where the agent file sits, relative to the playbook root.
    path: str = ""
