"""Inbound port: fetch one REF in detail."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.ref_doc import RefDoc

__all__ = ["GetRefPort"]


@runtime_checkable
class GetRefPort(Protocol):
    """Returns one parsed REF by name."""

    def execute(self, *, name: str) -> RefDoc: ...
