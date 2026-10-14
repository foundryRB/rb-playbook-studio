"""Raised when creating an artifact that already exists."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["AlreadyExistsError"]


class AlreadyExistsError(AppError):
    """The artifact exists; creation would overwrite it."""

    def __init__(self, entity_type: str, identifier: str) -> None:
        super().__init__(f"{entity_type} already exists: {identifier}")
        self.entity_type = entity_type
        self.identifier = identifier
