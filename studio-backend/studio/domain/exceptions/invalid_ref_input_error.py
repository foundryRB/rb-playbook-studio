"""Raised when new-REF input violates the naming or domain rules."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["InvalidRefInputError"]


class InvalidRefInputError(AppError):
    """The requested REF name or domain does not fit the conventions."""
