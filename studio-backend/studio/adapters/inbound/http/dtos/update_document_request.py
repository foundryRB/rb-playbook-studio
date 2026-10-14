"""Request DTO for replacing a whole REF document."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["UpdateDocumentRequest"]


class UpdateDocumentRequest(BaseModel):
    """The new full markdown content (frontmatter included) for one REF."""

    raw: str
