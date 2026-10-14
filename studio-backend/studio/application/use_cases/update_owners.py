"""Use case: replace OWNERS, the corpus's rights, behind its checks and the gates."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import OWNERS_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.invalid_owners_error import InvalidOwnersError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import OWNERS_FILE, Action, Owners
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["UpdateOwners"]

logger = get_logger(__name__)


class UpdateOwners:
    """The admin's edit of who may change what. Implements UpdateOwnersPort.

    A file that does not parse, or a line naming a path the corpus does not
    hold, is refused before anything is written: rights over a path that is not
    there are a typo waiting to grant something later. An accepted edit takes
    effect on the next request, since the rights are read from the corpus.
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
        """Check, write, gate and commit the new OWNERS; restore it if the gates fail."""
        with self._guard.write(actor, Action.ADMINISTER) as author:
            owners = Owners.parse(raw)
            missing = [
                rule for rule in owners.rules if not self._repository.path_exists(path=rule.path)
            ]
            if missing:
                lines = ", ".join(f"line {r.line} (/{r.path})" for r in missing)
                raise InvalidOwnersError(f"OWNERS names paths the playbook does not hold: {lines}")
            original = self._repository.read_owners()

            logger.info("Rewriting OWNERS (%d rule(s))", len(owners.rules))
            self._repository.write_owners(text=raw.rstrip("\n") + "\n")
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for OWNERS; rolling back")
                self._repository.write_owners(text=original)
                state_refusal(self._events, subject=OWNERS_FILE, kind="owners", report=report)
                raise ValidationFailedError(report)
            logger.info("OWNERS rewrite accepted")
            message = "chore(owners): replace OWNERS"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=OWNERS_UPDATED,
            subject=OWNERS_FILE,
            data={"owners": OWNERS_FILE, "commit": message},
        )
        return report
