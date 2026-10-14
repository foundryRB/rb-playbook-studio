"""Response DTO for the working clone's sync state."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["SyncStatusResponse"]


class SyncStatusResponse(BaseModel):
    """Unpushed commits, the diffstat a push would publish, and the upstream."""

    unpushed_commits: int
    diff_stat: str
    repo: str = ""
