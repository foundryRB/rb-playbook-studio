"""A REF pattern document."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.ref_domain import RefDomain
from studio.domain.model.ref_section import RefSection

__all__ = ["RefDoc"]


@dataclass(frozen=True)
class RefDoc:
    """A parsed REF-*.md: identity is `name` (e.g. 'REF-Python')."""

    name: str
    domain: RefDomain
    title: str
    summary: str
    sections: tuple[RefSection, ...]
    raw: str
    galaxy: str | None = None
    #: Where the REF sits in the corpus, relative to the playbook root.
    path: str = ""

    def section(self, number: int) -> RefSection | None:
        return next((s for s in self.sections if s.number == number), None)
