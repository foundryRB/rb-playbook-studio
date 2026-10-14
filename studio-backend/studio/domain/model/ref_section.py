"""One numbered section of a REF document."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["RefSection"]


@dataclass(frozen=True)
class RefSection:
    """A `## N. Title` section. `generated` marks machine-maintained sections."""

    number: int
    title: str
    body: str
    generated: bool

    @property
    def heading(self) -> str:
        return f"## {self.number}. {self.title}"
