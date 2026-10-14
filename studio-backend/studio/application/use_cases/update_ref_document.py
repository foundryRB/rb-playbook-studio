"""Use case: replace a whole REF document behind the validation gate."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import REF_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["UpdateRefDocument"]

logger = get_logger(__name__)


class UpdateRefDocument:
    """Whole-document editing: restructuring sections is just editing text.

    Implements UpdateRefDocumentPort. The template itself is enforced by the
    gates (INT-SHAPE numbering/frontmatter, INT-LAYER generated back-links),
    so any structural mistake rolls the file back rather than persisting.
    """

    def __init__(
        self,
        repository: PlaybookRepository,
        validator: PlaybookValidator,
        git: GitSync,
        guard: CorpusGuard,
        events: EventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._git = git
        self._guard = guard
        self._events = events

    def execute(self, *, actor: Actor | None, ref_name: str, raw: str) -> ValidationReport:
        """Write the full document; restore the original and raise if gates fail."""
        target = self._repository.get_ref(name=ref_name).path
        with self._guard.write(actor, Action.EDIT, target) as author:
            original = self._repository.get_ref(name=ref_name).raw

            logger.info("Rewriting %s (full document)", ref_name)
            self._repository.write_ref_document(ref_name=ref_name, raw=raw)
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for %s; rolling back", ref_name)
                self._repository.write_ref_document(ref_name=ref_name, raw=original)
                state_refusal(self._events, subject=ref_name, kind="ref", report=report)
                raise ValidationFailedError(report)
            logger.info("Rewrite of %s accepted by validation gates", ref_name)
            message = f"docs({ref_name}): replace document"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=REF_UPDATED,
            subject=ref_name,
            data={"ref": ref_name, "commit": message},
        )
        return report
