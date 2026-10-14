"""Use case: replace one galaxy's GALAXY.md behind the validation gate."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import GALAXY_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["UpdateGalaxyDocument"]

logger = get_logger(__name__)


class UpdateGalaxyDocument:
    """Gated editing of a galaxy's own routing document.

    Implements UpdateGalaxyDocumentPort. A GALAXY.md is not a scaffold artifact:
    it carries the routing table and the shelf's cross-cutting violations list,
    doctrine edited about as often as a REF section, so it is edited through the
    door rather than through a clone.

    The Available Skills table inside it is scripts/sync_registry.py's output and
    is not the caller's to author. INT-LAYER-006 refuses a table that is not what
    the generator would write, and INT-LAYER-003 refuses one that disagrees with
    the filesystem, so a write carrying a stale table rolls back like any other
    refusal. Read the document, edit the authored prose, and send the table back
    as it came. The studio does not regenerate it here, because a galaxy edit
    changes no skill frontmatter and so cannot be the thing that staled it.
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
        target = self._repository.get_galaxy(name=name).path
        with self._guard.write(actor, Action.EDIT, target) as author:
            original = self._repository.get_galaxy(name=name).raw

            logger.info("Rewriting GALAXY.md for %s", name)
            self._repository.write_galaxy_document(name=name, raw=raw)
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for galaxy %s; rolling back", name)
                self._repository.write_galaxy_document(name=name, raw=original)
                state_refusal(self._events, subject=name, kind="galaxy", report=report)
                raise ValidationFailedError(report)
            logger.info("Rewrite of galaxy %s accepted by validation gates", name)
            message = f"docs(galaxy): replace {name} GALAXY.md"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=GALAXY_UPDATED,
            subject=name,
            data={"galaxy": name, "commit": message},
        )
        return report
