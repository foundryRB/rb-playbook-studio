"""Inbound port: fetch the parsed playbook entry-point document."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.playbook_doc import PlaybookDoc

__all__ = ["GetPlaybookPort"]


@runtime_checkable
class GetPlaybookPort(Protocol):
    """Returns AI-PLAYBOOK.md parsed into titled sections."""

    def execute(self) -> PlaybookDoc: ...
