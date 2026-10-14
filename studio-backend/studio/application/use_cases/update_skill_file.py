"""Use case: edit one skill file behind the validation gate."""

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

__all__ = ["UpdateSkillFile"]

logger = get_logger(__name__)


class UpdateSkillFile:
    """Gated editing of any file inside a skill folder (scripts, themes, docs).

    Implements UpdateSkillFilePort. SKILL.md edits route here too when
    addressed as a file; the whole-document endpoint remains for convenience.
    A new file inside a skill is an edit of that skill, so its owner may add one.
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
        self, *, actor: Actor | None, name: str, rel_path: str, content: str
    ) -> ValidationReport:
        """Write the file; restore the prior state and raise if gates fail.

        The path may name a file the skill does not carry yet, which is how a
        skill grows the templates and scripts it ships. The prior state a
        rejected write restores is then the file's absence.

        SKILL.md arrives here whenever a caller addresses it as a file, so this
        path regenerates the back-link sections the way the whole-document one
        does (INT-DERIVE-002); the two routes write the same frontmatter.
        """
        target = self._repository.get_skill(name=name).path
        with self._guard.write(actor, Action.EDIT, target) as author:
            existed = self._repository.skill_file_exists(name=name, rel_path=rel_path)
            original = (
                self._repository.read_skill_file(name=name, rel_path=rel_path) if existed else None
            )
            verb = "edit" if existed else "add"
            refs_before = snapshot_refs(self._repository)

            logger.info("Writing skill file %s/%s (%s)", name, rel_path, verb)
            created_dirs = self._repository.write_skill_file(
                name=name, rel_path=rel_path, content=content
            )
            refused = regenerate(self._repository)
            report = refused if refused is not None else self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for %s/%s; rolling back", name, rel_path)
                if original is None:
                    self._repository.delete_skill_file(
                        name=name, rel_path=rel_path, created_dirs=created_dirs
                    )
                else:
                    self._repository.write_skill_file(
                        name=name, rel_path=rel_path, content=original
                    )
                restore_refs(self._repository, refs_before)
                state_refusal(self._events, subject=name, kind="skill", report=report)
                raise ValidationFailedError(report)
            logger.info("Write to %s/%s accepted by validation gates", name, rel_path)
            message = f"docs(skill): {verb} {name}/{rel_path}"
            self._git.commit_all(message=message, author=author)
        state_fact(
            self._events,
            event_type=SKILL_UPDATED,
            subject=name,
            data={"skill": name, "commit": message, "path": rel_path},
        )
        return report
