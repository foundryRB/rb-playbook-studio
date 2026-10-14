"""A nebula's full content: nebulae/<territory>/ with NEBULA.md and notes."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.nebula_note import NebulaNote

__all__ = ["NebulaDoc"]


@dataclass(frozen=True)
class NebulaDoc:
    """One territory's quarantined stardust: the fronting NEBULA.md plus notes.

    Unearned by definition (REF-Universe: the unearned zone). This document
    exists for the human surfaces only; it never crosses the MCP door and it
    never enters the reference graph.
    """

    territory: str
    subject: str
    raw: str
    notes: tuple[NebulaNote, ...]
