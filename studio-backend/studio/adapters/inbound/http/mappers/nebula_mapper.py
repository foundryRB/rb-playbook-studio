"""Mapper: domain nebula objects to their response DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from studio.adapters.inbound.http.dtos.nebula_detail_response import NebulaDetailResponse
from studio.adapters.inbound.http.dtos.nebula_note_response import NebulaNoteResponse
from studio.adapters.inbound.http.dtos.nebula_summary_response import NebulaSummaryResponse

if TYPE_CHECKING:
    from studio.domain.model.nebula_doc import NebulaDoc
    from studio.domain.model.nebula_note import NebulaNote
    from studio.domain.model.nebula_summary import NebulaSummary

__all__ = ["map_nebula", "map_nebula_summary"]


def map_nebula_summary(summary: NebulaSummary) -> NebulaSummaryResponse:
    """Convert a nebula roster summary to its response DTO."""
    return NebulaSummaryResponse(
        territory=summary.territory,
        subject=summary.subject,
        note_count=summary.note_count,
        unsmelted=summary.unsmelted,
        taken=summary.taken,
        burned=summary.burned,
    )


def _map_note(note: NebulaNote) -> NebulaNoteResponse:
    return NebulaNoteResponse(
        name=note.name,
        type=note.note_type,
        confidence=note.confidence,
        vote=note.vote,
        seats=list(note.seats),
        sources=list(note.sources),
        links=list(note.links),
        status=note.status,
        body=note.body,
    )


def map_nebula(nebula: NebulaDoc) -> NebulaDetailResponse:
    """Convert a parsed nebula document to its response DTO."""
    return NebulaDetailResponse(
        territory=nebula.territory,
        subject=nebula.subject,
        raw=nebula.raw,
        notes=[_map_note(n) for n in nebula.notes],
    )
