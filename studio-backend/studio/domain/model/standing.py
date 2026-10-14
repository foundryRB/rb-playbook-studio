"""Where an actor stands: who they are and what OWNERS lets them do."""

from __future__ import annotations

from dataclasses import dataclass

from studio.domain.model.actor import Actor
from studio.domain.model.rights import Role

__all__ = ["Standing"]


@dataclass(frozen=True)
class Standing:
    """The acting identity with its role and the rights a surface renders from.

    `galaxies` are the galaxies the actor may create atoms in; `atoms` the atom
    paths OWNERS names them for. The flags answer the acts that have no single
    atom to carry a `can_edit`: the playbook page, the sync acts and OWNERS
    (`can_administer`), and running the gates (`can_validate`).
    """

    actor: Actor
    role: Role
    galaxies: tuple[str, ...]
    atoms: tuple[str, ...]
    can_edit_playbook: bool
    can_administer: bool
    can_validate: bool
