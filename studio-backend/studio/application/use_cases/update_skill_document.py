"""Use case: replace a whole SKILL.md behind the validation gate."""

from __future__ import annotations

from studio.application.backlinks import regenerate, restore_refs, snapshot_refs
from studio.application.corpus_guard import CorpusGuard
from studio.application.events import SKILL_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["UpdateSkillDocument"]

logger = get_logger(__name__)


class UpdateSkillDocument:
    """Gated whole-document skill editing. Implements UpdateSkillDocumentPort.

    A skill's frontmatter (refs, description) is quoted by the generated
    back-link sections of every REF it cites, so the write path regenerates
    those sections from the playbook's own scripts/sync_backlinks.py before
    the gates read the corpus. The gates then judge a consistent corpus rather
    than refusing the edit for a staleness the edit itself caused.
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
        target = self._repository.get_skill(name=name).path
        with self._guard.write(actor, Action.EDIT, target) as author:
            original = self._repository.get_skill(name=name).raw
            refs_before = snapshot_refs(self._repository)

            logger.info("Rewriting skill %s (full document)", name)
            self._repository.write_skill_document(name=name, raw=raw)
            refused = regenerate(self._repository)
            report = refused if refused is not None else self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for skill %s; rolling back", name)
                self._repository.write_skill_document(name=name, raw=original)
                restore_refs(self._repository, refs_before)
                state_refusal(self._events, subject=name, kind="skill", report=report)
                raise ValidationFailedError(report)
            logger.info("Rewrite of skill %s accepted by validation gates", name)
            message = f"docs(skill): replace {name} SKILL.md"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=SKILL_UPDATED,
            subject=name,
            data={"skill": name, "commit": message},
        )
        return report
