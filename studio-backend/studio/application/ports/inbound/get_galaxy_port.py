"""Inbound port: fetch one galaxy's parsed routing document."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.galaxy_doc import GalaxyDoc

__all__ = ["GetGalaxyPort"]


@runtime_checkable
class GetGalaxyPort(Protocol):
    """Returns galaxies/<name>/GALAXY.md parsed into titled sections."""

    def execute(self, *, name: str) -> GalaxyDoc: ...
