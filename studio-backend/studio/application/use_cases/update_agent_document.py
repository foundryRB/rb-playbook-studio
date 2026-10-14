"""Use case: replace a whole agent document behind the validation gate."""

from __future__ import annotations

from studio.application.backlinks import regenerate, restore_refs, snapshot_refs
from studio.application.corpus_guard import CorpusGuard
from studio.application.events import AGENT_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["UpdateAgentDocument"]

logger = get_logger(__name__)


class UpdateAgentDocument:
    """Gated whole-document agent editing. Implements UpdateAgentDocumentPort.

    The gates carry the corpus's agent rules (the no-procedure cap among them)
    and the back-link sync checks; an edit that breaks either rolls back and
    surfaces the report. An agent's frontmatter is quoted by the generated
    back-link sections of every REF it cites, so the write path regenerates
    those sections from the playbook's own scripts/sync_backlinks.py before the
    gates read the corpus.
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

    def execute(self, *, actor: Actor | None, name: str, raw: str) -> ValidationReport:
        """Write the full document; restore the original and raise if gates fail."""
        target = self._repository.get_agent(name=name).path
        with self._guard.write(actor, Action.EDIT, target) as author:
            original = self._repository.get_agent(name=name).raw
            refs_before = snapshot_refs(self._repository)

            logger.info("Rewriting agent %s (full document)", name)
            self._repository.write_agent_document(name=name, raw=raw)
            refused = regenerate(self._repository)
            report = refused if refused is not None else self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for agent %s; rolling back", name)
                self._repository.write_agent_document(name=name, raw=original)
                restore_refs(self._repository, refs_before)
                state_refusal(self._events, subject=name, kind="agent", report=report)
                raise ValidationFailedError(report)
            logger.info("Rewrite of agent %s accepted by validation gates", name)
            message = f"docs(agent): replace {name}.md"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=AGENT_UPDATED,
            subject=name,
            data={"agent": name, "commit": message},
        )
        return report
