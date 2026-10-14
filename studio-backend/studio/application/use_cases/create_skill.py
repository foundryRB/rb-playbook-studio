"""Use case: author a new Skill behind the validation gate."""

from __future__ import annotations

import re

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import SKILL_CREATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.exceptions.invalid_ref_input_error import InvalidRefInputError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.node_kind import NodeKind
from studio.domain.model.rights import Action, check_owners, with_owners
from studio.domain.model.skill_doc import SkillDoc
from studio.logging import get_logger

__all__ = ["CreateSkill"]

logger = get_logger(__name__)

_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class CreateSkill:
    """Scaffolds via the playbook's own bootstrap-skill skill. Implements CreateSkillPort.

    bootstrap-skill is a three-artifact transaction (SKILL.md, playbook table
    row, regenerated back-links); this use case snapshots everything it can
    touch and restores all of it if the gates reject the result. Owners named
    at creation become one more OWNERS line in the same transaction.
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
        description: str,
        refs: list[str],
        galaxy: str = "craft",
        owners: list[str] | None = None,
    ) -> SkillDoc:
        """Scaffold skill + registry row + back-links; roll them all back on failure."""
        if not _NAME_RE.match(name):
            raise InvalidRefInputError(f"skill name must be kebab-case: {name!r}")
        if not description.strip():
            raise InvalidRefInputError("description is required")
        check_owners(owners or [])
        target = self._repository.planned_path(kind=NodeKind.SKILL, galaxy=galaxy, name=name)
        with self._guard.write(actor, Action.CREATE, target) as author:
            playbook_before = self._repository.get_playbook().raw
            refs_before = {r: self._repository.get_ref(name=r).raw for r in refs}
            owners_before = self._repository.read_owners()
            # bootstrap-skill writes the galaxy's registry row; snapshot that doc
            # too. A flat legacy corpus has no galaxy docs; only the craft
            # default may proceed without one.
            galaxy_before: str | None
            try:
                galaxy_before = self._repository.get_galaxy(name=galaxy).raw
            except EntityNotFoundError:
                if galaxy != "craft":
                    raise
                galaxy_before = None

            logger.info(
                "Scaffolding skill %s via bootstrap-skill (refs=%s, galaxy=%s)",
                name,
                refs,
                galaxy,
            )
            skill = self._repository.scaffold_skill(
                name=name, description=description.strip(), refs=refs, galaxy=galaxy
            )
            if owners:
                self._repository.write_owners(
                    text=with_owners(owners_before, path=skill.path, owners=owners, directory=True)
                )
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for new skill %s; rolling back", name)
                self._repository.delete_skill_document(name=name)
                self._repository.write_playbook_document(raw=playbook_before)
                if galaxy_before is not None:
                    self._repository.write_galaxy_document(name=galaxy, raw=galaxy_before)
                for ref_name, raw in refs_before.items():
                    self._repository.write_ref_document(ref_name=ref_name, raw=raw)
                if owners:
                    self._repository.write_owners(text=owners_before)
                state_refusal(self._events, subject=name, kind="skill", report=report)
                raise ValidationFailedError(report)
            logger.info("New skill %s accepted by validation gates", name)
            self._git.commit_all(message=f"feat(skill): {name}", author=author)
        state_fact(
            self._events,
            event_type=SKILL_CREATED,
            subject=name,
            data={"skill": name, "commit": f"feat(skill): {name}"},
        )
        return skill
