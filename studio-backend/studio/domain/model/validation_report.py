"""Outcome of running the playbook's deterministic gates."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ValidationReport"]


@dataclass(frozen=True)
class ValidationReport:
    """Result of the intent-test suite and the link checker."""

    tests_passed: bool
    links_ok: bool
    tests_output: str
    links_output: str

    @property
    def ok(self) -> bool:
        return self.tests_passed and self.links_ok
