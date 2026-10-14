"""Exception hierarchy barrel."""

from __future__ import annotations

from studio.domain.exceptions.already_exists_error import AlreadyExistsError
from studio.domain.exceptions.app_error import AppError
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.exceptions.forbidden_error import ForbiddenError
from studio.domain.exceptions.generated_section_error import GeneratedSectionError
from studio.domain.exceptions.invalid_owners_error import InvalidOwnersError
from studio.domain.exceptions.invalid_ref_input_error import InvalidRefInputError
from studio.domain.exceptions.not_authenticated_error import NotAuthenticatedError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError

__all__ = [
    "AlreadyExistsError",
    "AppError",
    "EntityNotFoundError",
    "ForbiddenError",
    "GeneratedSectionError",
    "InvalidOwnersError",
    "InvalidRefInputError",
    "NotAuthenticatedError",
    "ValidationFailedError",
]
