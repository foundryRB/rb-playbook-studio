"""Kinds of nodes in the playbook reference graph."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["NodeKind"]


class NodeKind(StrEnum):
    """What a graph node represents."""

    PLAYBOOK = "playbook"
    REF = "ref"
    SKILL = "skill"
    AGENT = "agent"
    MCP = "mcp"
    RAG = "rag"
