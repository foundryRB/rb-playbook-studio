"""One stardust note inside a nebula: nebulae/<territory>/<name>.md."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["NebulaNote"]


@dataclass(frozen=True)
class NebulaNote:
    """A typed research finding (REF-Forge stardust schema), parsed as-is.

    The studio renders the schema fields; it never enforces them (the corpus's
    own gates hold that line). `vote` is None on derived notes.
    """

    name: str
    note_type: str
    confidence: str
    vote: str | None
    seats: tuple[str, ...]
    sources: tuple[str, ...]
    links: tuple[str, ...]
    status: str
    body: str
