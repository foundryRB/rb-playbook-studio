"""Raised when the acting person's rights do not reach the act."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["ForbiddenError"]


class ForbiddenError(AppError):
    """The actor is known and OWNERS does not give them the target; the message
    names the role that would allow the act."""
