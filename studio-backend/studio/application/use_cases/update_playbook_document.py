"""Use case: replace AI-PLAYBOOK.md behind the validation gate."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import PLAYBOOK_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["PLAYBOOK_PATH", "UpdatePlaybookDocument"]

logger = get_logger(__name__)

#: The universe index, at the playbook root.
PLAYBOOK_PATH = "AI-PLAYBOOK.md"


class UpdatePlaybookDocument:
    """Gated editing of the entry-point document itself (routing, violations).

    Implements UpdatePlaybookDocumentPort. INT-LAYER-003 keeps the Available
    Skills table honest; a table edit that orphans a skill rolls back.
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

    def execute(self, *, actor: Actor | None, raw: str) -> ValidationReport:
        """Write the full document; restore the original and raise if gates fail."""
        with self._guard.write(actor, Action.EDIT, PLAYBOOK_PATH) as author:
            original = self._repository.get_playbook().raw

            logger.info("Rewriting AI-PLAYBOOK.md")
            self._repository.write_playbook_document(raw=raw)
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for AI-PLAYBOOK.md; rolling back")
                self._repository.write_playbook_document(raw=original)
                state_refusal(self._events, subject=PLAYBOOK_PATH, kind="playbook", report=report)
                raise ValidationFailedError(report)
            logger.info("AI-PLAYBOOK.md rewrite accepted by validation gates")
            message = "docs(playbook): replace AI-PLAYBOOK.md"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=PLAYBOOK_UPDATED,
            subject=PLAYBOOK_PATH,
            data={"playbook": PLAYBOOK_PATH, "commit": message},
        )
        return report
