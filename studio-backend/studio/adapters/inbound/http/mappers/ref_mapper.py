"""Mapper: domain RefDoc to RefDetailResponse DTO."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.ref_detail_response import RefDetailResponse
from studio.adapters.inbound.http.dtos.ref_section_response import RefSectionResponse

if TYPE_CHECKING:
    from studio.domain.model.ref_doc import RefDoc

__all__ = ["map_ref"]


def map_ref(ref: RefDoc, *, can_edit: bool = False) -> RefDetailResponse:
    """Convert a parsed REF to its response DTO."""
    return RefDetailResponse(
        name=ref.name,
        domain=str(ref.domain),
        title=ref.title,
        summary=ref.summary,
        raw=ref.raw,
        can_edit=can_edit,
        galaxy=ref.galaxy,
        sections=[
            RefSectionResponse(
                number=s.number, title=s.title, body=s.body, generated=s.generated
            )
            for s in ref.sections
        ],
    )
