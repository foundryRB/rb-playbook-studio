"""Request DTO for declaring a new MCP or RAG card."""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["CreateDoorRequest"]


class CreateDoorRequest(BaseModel):
    """The card's kind, name, galaxy and whole document, and who will own it."""

    kind: str = Field(description="'mcp' (a door) or 'rag' (a retrieval seat)")
    name: str
    galaxy: str
    raw: str
    owners: list[str] = Field(
        default_factory=list, description="Emails OWNERS will name as the card's owners"
    )
