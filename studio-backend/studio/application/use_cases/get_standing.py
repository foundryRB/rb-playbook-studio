"""Use case: who is acting, and what OWNERS lets them do."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.application.use_cases.update_playbook_document import PLAYBOOK_PATH
from studio.domain.exceptions.not_authenticated_error import NotAuthenticatedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.standing import Standing

__all__ = ["GetStanding"]


class GetStanding:
    """Implements GetStandingPort: the facts a surface renders its controls from."""

    def __init__(self, repository: PlaybookRepository, guard: CorpusGuard) -> None:
        self._repository = repository
        self._guard = guard

    def execute(self, *, actor: Actor | None) -> Standing:
        if actor is None:
            raise NotAuthenticatedError("nobody is signed in")
        owners = self._guard.owners()
        return Standing(
            actor=actor,
            role=owners.role_of(actor),
            galaxies=tuple(owners.galaxies_written(actor, self._repository.list_galaxies())),
            atoms=tuple(owners.atoms_owned(actor)),
            can_edit_playbook=owners.may(actor, Action.EDIT, PLAYBOOK_PATH),
            can_administer=owners.may(actor, Action.ADMINISTER),
            can_validate=owners.may(actor, Action.VALIDATE),
        )
