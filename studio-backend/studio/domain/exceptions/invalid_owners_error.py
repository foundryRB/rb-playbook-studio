"""Raised when OWNERS text does not parse, or names a path the corpus lacks."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["InvalidOwnersError"]


class InvalidOwnersError(AppError):
    """The rights file is refused as written; the message names the line."""
