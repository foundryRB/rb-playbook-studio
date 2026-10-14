"""A nebula's roster summary, for the list surface and the maps."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["NebulaSummary"]


@dataclass(frozen=True)
class NebulaSummary:
    """One territory under study: its subject line and stardust status counts.

    The status fields mirror the stardust schema's closed list (REF-Forge:
    unsmelted, taken, burned); a note with any other status still counts in
    `note_count`, so the roster never under-reports.
    """

    territory: str
    subject: str
    note_count: int
    unsmelted: int
    taken: int
    burned: int
