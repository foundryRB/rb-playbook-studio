"""Canonical domain classification of a REF (its `domain:` frontmatter)."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["RefDomain"]


class RefDomain(StrEnum):
    """The canonical `domain:` values a REF may declare (INT-SHAPE-004)."""

    META = "meta"
    ARCHITECTURE = "architecture"
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    PRACTICE = "practice"
    METHODOLOGY = "methodology"
    PKM = "pkm"
