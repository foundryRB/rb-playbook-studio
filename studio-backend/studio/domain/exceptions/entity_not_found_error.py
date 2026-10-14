"""A required entity or record could not be found."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError

__all__ = ["EntityNotFoundError"]


class EntityNotFoundError(AppError):
    """A required entity or record could not be found."""

    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} not found: {identifier}")
