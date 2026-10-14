"""Response DTO for a freshly minted personal token."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["PersonalTokenResponse"]


class PersonalTokenResponse(BaseModel):
    """The token (shown once), whose it is, and when it ends (UTC, ISO 8601)."""

    token: str
    email: str
    name: str
    expires_at: str
