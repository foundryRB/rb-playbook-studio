"""A galaxy's routing document: galaxies/<name>/GALAXY.md."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.playbook_section import PlaybookSection

__all__ = ["GalaxyDoc"]


@dataclass(frozen=True)
class GalaxyDoc:
    """A parsed GALAXY.md: the galaxy's routing table and registries."""

    name: str
    title: str
    sections: tuple[PlaybookSection, ...]
    raw: str
    #: The galaxy page, relative to the playbook root.
    path: str = ""
