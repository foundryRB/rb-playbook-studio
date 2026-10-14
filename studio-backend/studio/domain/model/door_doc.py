"""A declared door planet: an mcps/<name>.md or rags/<name>.md file."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.node_kind import NodeKind

__all__ = ["DoorDoc"]


@dataclass(frozen=True)
class DoorDoc:
    """A galaxy's declared door: name, purpose, and doctrine; never interface or binding."""

    name: str
    kind: NodeKind
    galaxy: str
    refs: tuple[str, ...]
    summary: str
    raw: str
    #: Where the card sits, relative to the playbook root.
    path: str = ""
