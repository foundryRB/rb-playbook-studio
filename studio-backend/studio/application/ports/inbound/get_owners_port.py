"""Inbound port: read the corpus's OWNERS file."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["GetOwnersPort"]


@runtime_checkable
class GetOwnersPort(Protocol):
    """Returns the OWNERS text, or None when the playbook has none."""

    def execute(self) -> str | None: ...
