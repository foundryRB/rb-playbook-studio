"""Raised when the remote rejects a push because upstream moved."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["SyncRejectedError"]


class SyncRejectedError(AppError):
    """Non-fast-forward rejection; reconcile with upstream and push again."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"push rejected by upstream: {detail}")
