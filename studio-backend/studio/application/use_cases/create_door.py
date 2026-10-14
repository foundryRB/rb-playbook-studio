"""Use case: declare a new MCP or RAG card behind the validation gate."""

from __future__ import annotations

import re

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import DOOR_CREATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.invalid_ref_input_error import InvalidRefInputError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.door_doc import DoorDoc
from studio.domain.model.node_kind import NodeKind
from studio.domain.model.rights import Action, check_owners, with_owners
from studio.logging import get_logger

__all__ = ["CreateDoor"]

logger = get_logger(__name__)

_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_KINDS = {"mcp": NodeKind.MCP, "rag": NodeKind.RAG}


class CreateDoor:
    """Files a new declaration card in a galaxy. Implements CreateDoorPort.

    The playbook carries no scaffolder for cards, so the caller sends the whole
    card (frontmatter and doctrine, REF-Universe section 3) and the gates judge
    it like every other edit. Owners named at creation become one more OWNERS
    line in the same transaction.
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

    def execute(
        self,
        *,
        actor: Actor | None,
        kind: str,
        name: str,
        galaxy: str,
        raw: str,
        owners: list[str] | None = None,
    ) -> DoorDoc:
        """Write the card (and its owners line); remove both again if the gates fail."""
        node_kind = _KINDS.get(kind)
        if node_kind is None:
            raise InvalidRefInputError(f"a card is an 'mcp' or a 'rag', not {kind!r}")
        if not _NAME_RE.match(name):
            raise InvalidRefInputError(f"card name must be kebab-case: {name!r}")
        if not raw.strip():
            raise InvalidRefInputError("the card's document is required")
        check_owners(owners or [])
        target = self._repository.planned_path(kind=node_kind, galaxy=galaxy, name=name)
        with self._guard.write(actor, Action.CREATE, target) as author:
            owners_before = self._repository.read_owners()

            logger.info("Declaring %s card %s in %s", kind, name, galaxy)
            door = self._repository.create_door_document(
                kind=node_kind, galaxy=galaxy, name=name, raw=raw
            )
            if owners:
                self._repository.write_owners(
                    text=with_owners(owners_before, path=door.path, owners=owners, directory=False)
                )
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for new card %s; removing it", name)
                self._repository.delete_door_document(name=name)
                if owners:
                    self._repository.write_owners(text=owners_before)
                state_refusal(self._events, subject=name, kind=kind, report=report)
                raise ValidationFailedError(report)
            logger.info("New card %s accepted by validation gates", name)
            message = f"feat({kind}): {name}"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=DOOR_CREATED,
            subject=name,
            data={"door": name, "kind": kind, "commit": message},
        )
        return door
