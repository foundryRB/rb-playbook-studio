"""Use case: author a new Agent behind the validation gate."""

from __future__ import annotations

import re

from studio.application.corpus_guard import CorpusGuard
from studio.application.events import AGENT_CREATED, state_fact, state_refusal
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.domain.exceptions.invalid_ref_input_error import InvalidRefInputError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.agent_doc import AgentDoc
from studio.domain.model.node_kind import NodeKind
from studio.domain.model.rights import Action, check_owners, with_owners
from studio.logging import get_logger

__all__ = ["CreateAgent"]

logger = get_logger(__name__)

_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class CreateAgent:
    """Scaffolds via the playbook's own bootstrap-agent skill. Implements CreateAgentPort.

    bootstrap-agent is a two-artifact transaction (the agent file, regenerated
    back-links in every cited REF); this use case snapshots the REFs it can
    touch and restores all of it if the gates reject the result. The gates
    include the corpus's own no-procedure rule, so an agent body that restates
    its skill's steps rolls back here like any other rejected edit. Owners
    named at creation become one more OWNERS line in the same transaction.
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
        title: str,
        description: str,
        refs: list[str],
        skills: list[str],
        doors: list[str] | None = None,
        galaxy: str = "craft",
        permission: str | None = None,
        writes: bool = False,
        fresh_eyes: bool = False,
        hair: str | None = None,
        headwear: str | None = None,
        eyes: str | None = None,
        face: str | None = None,
        owners: list[str] | None = None,
    ) -> AgentDoc:
        """Scaffold agent + back-links; roll them all back on failure."""
        if not _NAME_RE.match(name):
            raise InvalidRefInputError(f"agent name must be kebab-case: {name!r}")
        if not title.strip():
            raise InvalidRefInputError("title is required")
        if not description.strip():
            raise InvalidRefInputError("description is required; a harness routes on it")
        check_owners(owners or [])
        target = self._repository.planned_path(kind=NodeKind.AGENT, galaxy=galaxy, name=name)
        with self._guard.write(actor, Action.CREATE, target) as author:
            refs_before = {r: self._repository.get_ref(name=r).raw for r in refs}
            owners_before = self._repository.read_owners()

            logger.info(
                "Scaffolding agent %s via bootstrap-agent (refs=%s, skills=%s, galaxy=%s)",
                name,
                refs,
                skills,
                galaxy,
            )
            agent = self._repository.scaffold_agent(
                name=name,
                title=title.strip(),
                description=" ".join(description.split()),
                refs=refs,
                skills=skills,
                doors=doors or [],
                galaxy=galaxy,
                permission=permission,
                writes=writes,
                fresh_eyes=fresh_eyes,
                hair=hair,
                headwear=headwear,
                eyes=eyes,
                face=face,
            )
            if owners:
                self._repository.write_owners(
                    text=with_owners(owners_before, path=agent.path, owners=owners, directory=False)
                )
            report = self._validator.validate()
            if not report.ok:
                logger.warning("Validation failed for new agent %s; rolling back", name)
                self._repository.delete_agent_document(name=name)
                for ref_name, raw in refs_before.items():
                    self._repository.write_ref_document(ref_name=ref_name, raw=raw)
                if owners:
                    self._repository.write_owners(text=owners_before)
                state_refusal(self._events, subject=name, kind="agent", report=report)
                raise ValidationFailedError(report)
            logger.info("New agent %s accepted by validation gates", name)
            self._git.commit_all(message=f"feat(agent): {name}", author=author)
        state_fact(
            self._events,
            event_type=AGENT_CREATED,
            subject=name,
            data={"agent": name, "commit": f"feat(agent): {name}"},
        )
        return agent
