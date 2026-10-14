"""Mapper: domain ValidationReport to ValidationReportResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.validation_report_response import ValidationReportResponse

if TYPE_CHECKING:
    from studio.domain.model.validation_report import ValidationReport

__all__ = ["map_validation_report"]


def map_validation_report(report: ValidationReport) -> ValidationReportResponse:
    """Convert a validation report to its response DTO."""
    return ValidationReportResponse(
        ok=report.ok,
        tests_passed=report.tests_passed,
        links_ok=report.links_ok,
        tests_output=report.tests_output,
        links_output=report.links_output,
    )
