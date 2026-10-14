"""Response DTO for one REF in detail."""

from __future__ import annotations

from pydantic import BaseModel

from studio.adapters.inbound.http.dtos.ref_section_response import RefSectionResponse

__all__ = ["RefDetailResponse"]


class RefDetailResponse(BaseModel):
    """A parsed REF returned over HTTP."""

    name: str
    domain: str
    title: str
    summary: str
    sections: list[RefSectionResponse]
    raw: str
    #: Whether the reader may change this document (OWNERS); controls render from it.
    can_edit: bool
    galaxy: str | None = None
