"""Mapper: domain GalaxyDoc to GalaxyResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.galaxy_response import GalaxyResponse
from studio.adapters.inbound.http.dtos.playbook_section_response import PlaybookSectionResponse

if TYPE_CHECKING:
    from studio.domain.model.galaxy_doc import GalaxyDoc

__all__ = ["map_galaxy"]


def map_galaxy(galaxy: GalaxyDoc, *, can_edit: bool = False) -> GalaxyResponse:
    """Convert a parsed galaxy document to its response DTO."""
    return GalaxyResponse(
        name=galaxy.name,
        title=galaxy.title,
        sections=[
            PlaybookSectionResponse(title=s.title, body=s.body) for s in galaxy.sections
        ],
        raw=galaxy.raw,
        can_edit=can_edit,
    )
