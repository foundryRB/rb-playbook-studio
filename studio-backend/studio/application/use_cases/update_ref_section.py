"""Use case: edit one REF section behind the validation gate."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import REF_UPDATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.exceptions.generated_section_error import GeneratedSectionError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["UpdateRefSection"]

logger = get_logger(__name__)


class UpdateRefSection:
    """Trusted-output editing: write, validate, roll back on failure.

    Implements UpdateRefSectionPort. The edit only survives if the playbook's
    own deterministic gates (intent tests + link checker) still pass.
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
        self, *, actor: Actor | None, ref_name: str, number: int, body: str
    ) -> ValidationReport:
        """Write the section body; restore the original document verbatim on failure."""
        target = self._repository.get_ref(name=ref_name).path
        with self._guard.write(actor, Action.EDIT, target) as author:
            ref = self._repository.get_ref(name=ref_name)
            section = ref.section(number)
            if section is None:
                raise EntityNotFoundError("section", f"{ref_name} §{number}")
            if section.generated:
                raise GeneratedSectionError(ref_name, number)

            logger.info("Editing %s section %d", ref_name, number)
            self._repository.write_ref_section(ref_name=ref_name, number=number, body=body)
            report = self._validator.validate()
            if not report.ok:
                logger.warning(
                    "Validation failed for %s section %d; rolling back", ref_name, number
                )
                # Restore the whole document byte-for-byte from the snapshot.
                # Rolling back through write_ref_section() is not a reliable
                # inverse: a body that itself contains a section heading makes
                # the rollback's span detection stop at the injected heading and
                # leave a duplicated section behind -- a rejected edit that
                # corrupts the working clone and jams every subsequent git pull.
                # A raw restore cannot corrupt.
                self._repository.write_ref_document(ref_name=ref_name, raw=ref.raw)
                state_refusal(self._events, subject=ref_name, kind="ref", report=report)
                raise ValidationFailedError(report)
            logger.info("Edit to %s section %d accepted by validation gates", ref_name, number)
            message = f"docs({ref_name}): edit section {number}"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=REF_UPDATED,
            subject=ref_name,
            data={"ref": ref_name, "commit": message, "section": number},
        )
        return report
