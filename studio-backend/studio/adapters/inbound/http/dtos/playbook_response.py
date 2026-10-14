"""Response DTO for the playbook document."""

from __future__ import annotations

from pydantic import BaseModel

from studio.adapters.inbound.http.dtos.playbook_section_response import PlaybookSectionResponse

__all__ = ["PlaybookResponse"]


class PlaybookResponse(BaseModel):
    """The parsed AI-PLAYBOOK.md returned over HTTP."""

    title: str
    sections: list[PlaybookSectionResponse]
    raw: str
    #: Whether the reader may change this document (OWNERS); controls render from it.
    can_edit: bool
