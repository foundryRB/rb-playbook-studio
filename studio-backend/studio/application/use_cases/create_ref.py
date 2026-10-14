"""Use case: author a new REF behind the validation gate."""

from __future__ import annotations

import re

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import REF_CREATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.exceptions.invalid_ref_input_error import InvalidRefInputError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.node_kind import NodeKind
from studio.domain.model.ref_doc import RefDoc
from studio.domain.model.ref_domain import RefDomain
from studio.domain.model.rights import Action
from studio.logging import get_logger

__all__ = ["CreateRef"]

logger = get_logger(__name__)

_NAME_RE = re.compile(r"^REF-[A-Z][A-Za-z0-9-]*$")


class CreateRef:
    """Scaffolds via the playbook's own bootstrap-ref skill. Implements CreateRefPort.

    The template lives in the playbook, not here; the studio only runs the
    skill's deterministic script and wraps it in the gate + rollback.
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
        name: str,
        domain: str,
        title: str,
        summary: str,
        galaxy: str = "craft",
    ) -> RefDoc:
        """Scaffold the file, run the gates, and remove it again if they fail."""
        if not _NAME_RE.match(name):
            raise InvalidRefInputError(f"REF name must match REF-<PascalCase>: {name!r}")
        try:
            RefDomain(domain)
        except ValueError as exc:
            raise InvalidRefInputError(f"unknown domain {domain!r}") from exc
        if not title.strip() or not summary.strip():
            raise InvalidRefInputError("title and summary are required")
        target = self._repository.planned_path(kind=NodeKind.REF, galaxy=galaxy, name=name)
        with self._guard.write(actor, Action.CREATE, target) as author:
            # Snapshot the galaxy's routing doc: bootstrap-ref adds a row to it,
            # and a gate failure must roll that back too. A flat legacy corpus
            # has no galaxy docs; only the craft default may proceed without one.
            galaxy_before: str | None
            try:
                galaxy_before = self._repository.get_galaxy(name=galaxy).raw
            except EntityNotFoundError:
                if galaxy != "craft":
                    raise
                galaxy_before = None

            logger.info(
                "Scaffolding %s via bootstrap-ref (domain=%s, galaxy=%s)", name, domain, galaxy
            )
            ref = self._repository.scaffold_ref(
                name=name,
                domain=domain,
                title=title.strip(),
                summary=summary.strip(),
                galaxy=galaxy,
            )
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for new %s; removing it", name)
                self._repository.delete_ref_document(ref_name=name)
                if galaxy_before is not None:
                    self._repository.write_galaxy_document(name=galaxy, raw=galaxy_before)
                state_refusal(self._events, subject=name, kind="ref", report=report)
                raise ValidationFailedError(report)
            logger.info("New %s accepted by validation gates", name)
            self._git.commit_all(message=f"feat(ref): {name}", author=author)
        state_fact(
            self._events,
            event_type=REF_CREATED,
            subject=name,
            data={"ref": name, "commit": f"feat(ref): {name}"},
        )
        return ref
