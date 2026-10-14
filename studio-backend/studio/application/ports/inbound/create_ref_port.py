"""Inbound port: author a new REF behind the validation gate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.actor import Actor
from studio.domain.model.ref_doc import RefDoc

__all__ = ["CreateRefPort"]


@runtime_checkable
class CreateRefPort(Protocol):
    """Creates a template-conformant REF; removes it and raises if gates fail."""

    def execute(
        self,
        *,
        actor: Actor | None,
        name: str,
        domain: str,
        title: str,
        summary: str,
        galaxy: str = "craft",
    ) -> RefDoc: ...
