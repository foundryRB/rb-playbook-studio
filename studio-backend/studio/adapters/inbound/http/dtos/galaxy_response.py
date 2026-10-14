"""Response DTO for one galaxy's routing document."""

from __future__ import annotations

from pydantic import BaseModel

from studio.adapters.inbound.http.dtos.playbook_section_response import PlaybookSectionResponse

__all__ = ["GalaxyResponse"]


class GalaxyResponse(BaseModel):
    """A parsed GALAXY.md returned over HTTP."""

    name: str
    title: str
    sections: list[PlaybookSectionResponse]
    raw: str
    #: Whether the reader may change this document (OWNERS); controls render from it.
    can_edit: bool
