"""Raised on attempts to edit a machine-generated section."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["GeneratedSectionError"]


class GeneratedSectionError(AppError):
    """The section is maintained by scripts/sync_backlinks.py, not by hand."""

    def __init__(self, ref_name: str, number: int) -> None:
        super().__init__(
            f"{ref_name} section {number} is machine-generated; edit skill frontmatter instead"
        )
        self.ref_name = ref_name
        self.number = number
