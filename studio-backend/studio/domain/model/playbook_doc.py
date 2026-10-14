"""The playbook entry-point document."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.playbook_section import PlaybookSection

__all__ = ["PlaybookDoc"]


@dataclass(frozen=True)
class PlaybookDoc:
    """Parsed AI-PLAYBOOK.md: the routing and governance document."""

    title: str
    sections: tuple[PlaybookSection, ...]
    raw: str
