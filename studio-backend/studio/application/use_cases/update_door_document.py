"""Use case: replace an MCP or RAG card behind the validation gate."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import DOOR_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["UpdateDoorDocument"]

logger = get_logger(__name__)


class UpdateDoorDocument:
    """Gated whole-document editing of a declared door. Implements UpdateDoorDocumentPort.

    An MCP or RAG card is a declaration (frontmatter, purpose and the earned
    doctrine; REF-Universe section 3) edited like an agent document: the gates
    judge it, a refusal restores it, and an accepted edit is one commit by its
    author. The card keeps its name, because the name is how the corpus and
    every agent's `doors:` find it.
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
        """Write the full card; restore the original and raise if the gates fail."""
        target = self._repository.get_door(name=name).path
        with self._guard.write(actor, Action.EDIT, target) as author:
            door = self._repository.get_door(name=name)

            logger.info("Rewriting %s card %s", door.kind, name)
            self._repository.write_door_document(name=name, raw=raw)
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for card %s; rolling back", name)
                self._repository.write_door_document(name=name, raw=door.raw)
                state_refusal(self._events, subject=name, kind=str(door.kind), report=report)
                raise ValidationFailedError(report)
            logger.info("Rewrite of card %s accepted by validation gates", name)
            message = f"docs({door.kind}): replace {name}.md"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=DOOR_UPDATED,
            subject=name,
            data={"door": name, "kind": str(door.kind), "commit": message},
        )
        return report
