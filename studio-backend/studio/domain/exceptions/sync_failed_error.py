"""Raised when a git sync operation fails for a non-conflict reason."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["SyncFailedError"]


class SyncFailedError(AppError):
    """Transport, auth, or unexpected git failure during sync."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"git sync failed: {detail}")
