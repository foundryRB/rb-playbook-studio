"""Response DTO for who is acting and what they may do."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["StandingResponse"]


class StandingResponse(BaseModel):
    """The acting identity, its role, and the rights the UI renders its controls from."""

    name: str
    email: str
    #: The studio's own identity (the shared credential, the stand-alone gate).
    service: bool
    role: str
    #: Galaxies this actor may create atoms in.
    galaxies: list[str]
    #: Atom paths OWNERS names this actor for.
    atoms: list[str]
    can_edit_playbook: bool
    #: OWNERS and the sync acts (push, refresh).
    can_administer: bool
    can_validate: bool
    #: Whether this studio mints personal tokens.
    tokens: bool
