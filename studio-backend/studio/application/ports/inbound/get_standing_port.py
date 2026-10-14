"""Inbound port: who is acting, and what OWNERS lets them do."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.standing import Standing

__all__ = ["GetStandingPort"]


@runtime_checkable
class GetStandingPort(Protocol):
    """Returns the actor's role, galaxies, atoms and the flags controls render from."""

    def execute(self, *, actor: Actor | None) -> Standing: ...
