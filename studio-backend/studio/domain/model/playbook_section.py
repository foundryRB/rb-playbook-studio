"""One `## ` section of the playbook entry-point document."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PlaybookSection"]


@dataclass(frozen=True)
class PlaybookSection:
    """A titled section of AI-PLAYBOOK.md."""

    title: str
    body: str
