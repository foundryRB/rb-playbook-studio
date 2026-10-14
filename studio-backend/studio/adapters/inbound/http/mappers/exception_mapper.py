"""Mapping from domain exceptions to HTTP status codes."""

from __future__ import annotations

from studio.domain.exceptions.already_exists_error import AlreadyExistsError
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.exceptions.forbidden_error import ForbiddenError
from studio.domain.exceptions.generated_section_error import GeneratedSectionError
from studio.domain.exceptions.invalid_owners_error import InvalidOwnersError
from studio.domain.exceptions.invalid_ref_input_error import InvalidRefInputError
from studio.domain.exceptions.not_authenticated_error import NotAuthenticatedError
from studio.domain.exceptions.sync_conflict_error import SyncConflictError
from studio.domain.exceptions.sync_failed_error import SyncFailedError
from studio.domain.exceptions.sync_rejected_error import SyncRejectedError
from studio.domain.exceptions.unsupported_capability_error import UnsupportedCapabilityError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError

__all__ = ["STATUS_MAP", "DEFAULT_STATUS"]

STATUS_MAP: dict[type[Exception], int] = {
    AlreadyExistsError: 409,
    EntityNotFoundError: 404,
    ForbiddenError: 403,
    GeneratedSectionError: 409,
    InvalidOwnersError: 400,
    InvalidRefInputError: 400,
    NotAuthenticatedError: 401,
    SyncConflictError: 409,
    SyncRejectedError: 409,
    SyncFailedError: 502,
    UnsupportedCapabilityError: 409,
    ValidationFailedError: 422,
}
DEFAULT_STATUS = 500
