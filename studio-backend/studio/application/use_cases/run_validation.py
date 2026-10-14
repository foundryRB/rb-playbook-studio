"""Use case: run the playbook validation gates on demand."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["RunValidation"]

logger = get_logger(__name__)


class RunValidation:
    """Runs intent tests + link checker. Implements RunValidationPort.

    Anyone who may write somewhere may run the gates; the run holds the corpus
    so it judges a tree no write is halfway through.
    """

    def __init__(self, validator: PlaybookValidator, guard: CorpusGuard) -> None:
        self._validator = validator
        self._guard = guard

    def execute(self, *, actor: Actor | None) -> ValidationReport:
        """Run both gates and return the combined report."""
        with self._guard.write(actor, Action.VALIDATE):
            report = self._validator.validate()
        if report.ok:
            logger.info("Playbook validation passed")
        else:
            logger.warning(
                "Playbook validation failed (tests_passed=%s, links_ok=%s)",
                report.tests_passed,
                report.links_ok,
            )
        return report
