"""Response DTO for a validation run."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["ValidationReportResponse"]


class ValidationReportResponse(BaseModel):
    """Outcome of the playbook's validation gates returned over HTTP."""

    ok: bool
    tests_passed: bool
    links_ok: bool
    tests_output: str
    links_output: str
