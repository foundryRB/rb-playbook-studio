"""A directed reference between two playbook artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.edge_kind import EdgeKind

__all__ = ["ReferenceEdge"]


@dataclass(frozen=True)
class ReferenceEdge:
    """Directed edge: `source` references `target` (node ids)."""

    source: str
    target: str
    kind: EdgeKind
