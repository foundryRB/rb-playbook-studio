"""Raised when a write arrives with no trusted identity."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["NotAuthenticatedError"]


class NotAuthenticatedError(AppError):
    """Nobody the studio trusts is acting, so no write can be attributed or allowed."""

    def __init__(self, message: str = "sign in to change the playbook") -> None:
        super().__init__(message)
