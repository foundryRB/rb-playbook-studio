"""Raised when an edit fails the playbook's validation gates."""

from __future__ import annotations

from studio.domain.exceptions.app_error import AppError
from studio.domain.model.validation_report import ValidationReport

__all__ = ["ValidationFailedError"]


class ValidationFailedError(AppError):
    """The edit was rolled back because the intent tests or link checker failed."""

    def __init__(self, report: ValidationReport) -> None:
        super().__init__("validation failed; edit rolled back")
        self.report = report
