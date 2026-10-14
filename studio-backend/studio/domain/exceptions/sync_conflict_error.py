"""Raised when reconciling with upstream hits a real merge conflict."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["SyncConflictError"]


class SyncConflictError(AppError):
    """Upstream and local history both changed the same content.

    Surfaces raw (no automatic resolution): the caller gets the conflicting
    files and reconciles history deliberately.
    """

    def __init__(self, files: list[str]) -> None:
        self.files = files
        listing = ", ".join(files) if files else "unknown files"
        super().__init__(f"sync conflict with upstream in: {listing}")
