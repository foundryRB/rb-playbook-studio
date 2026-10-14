"""Raised when a request names a capability this composition does not wire."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["UnsupportedCapabilityError"]


class UnsupportedCapabilityError(AppError):
    """The operation exists in another composition of this application."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
