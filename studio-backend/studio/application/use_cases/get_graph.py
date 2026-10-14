"""Use case: assemble the playbook reference graph."""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.graph_node import GraphNode
from studio.domain.model.node_kind import NodeKind
from studio.domain.model.playbook_graph import PlaybookGraph
from studio.logging import get_logger

__all__ = ["GetGraph"]

logger = get_logger(__name__)

_PLAYBOOK_NODE_ID = "AI-PLAYBOOK"


class GetGraph:
    """Builds the node/edge graph. Implements GetGraphPort."""

    def __init__(self, repository: PlaybookRepository) -> None:
        self._repository = repository

    def execute(self) -> PlaybookGraph:
        """Return the playbook root, every REF, skill, agent, door, and all edges."""
        root = GraphNode(
            id=_PLAYBOOK_NODE_ID,
            kind=NodeKind.PLAYBOOK,
            label="AI Playbook",
            domain=None,
            summary="The routing and governance entry point.",
        )
        nodes: list[GraphNode] = [root]
        nodes += [
            GraphNode(
                id=ref.name,
                kind=NodeKind.REF,
                label=ref.title,
                domain=ref.domain,
                summary=ref.summary,
                galaxy=ref.galaxy,
            )
            for ref in self._repository.list_refs()
        ]
        nodes += [
            GraphNode(
                id=skill.name,
                kind=NodeKind.SKILL,
                label=skill.name,
                domain=None,
                summary=skill.description,
                galaxy=skill.galaxy,
                moons=tuple(f for f in skill.files if f != "SKILL.md"),
            )
            for skill in self._repository.list_skills()
        ]
        nodes += [
            GraphNode(
                id=door.name,
                kind=door.kind,
                label=door.name,
                domain=None,
                summary=door.summary,
                galaxy=door.galaxy,
            )
            for door in self._repository.list_doors()
        ]
        nodes += [
            GraphNode(
                id=agent.name,
                kind=NodeKind.AGENT,
                label=agent.name,
                domain=None,
                summary=agent.summary,
                galaxy=agent.galaxy,
                fresh_eyes=agent.posture.fresh_eyes,
            )
            for agent in self._repository.list_agents()
        ]
        edges = tuple(self._repository.list_edges())
        logger.info("Graph assembled: %d nodes, %d edges", len(nodes), len(edges))
        return PlaybookGraph(nodes=tuple(nodes), edges=edges)
