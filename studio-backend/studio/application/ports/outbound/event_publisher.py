"""Outbound port: state a fact about this studio's own domain on the event bus."""

from __future__ import annotations

from typing import Protocol

__all__ = ["EventPublisher"]


class EventPublisher(Protocol):
    """Publish one past-tense fact, and never make the caller wait on it.

    The contract is REF-Events. An implementation MUST NOT raise, block past a
    short bound, or otherwise change the outcome of the act that caused the
    publish (section 6): a publish that cannot be delivered is dropped and
    logged, and no edit's acceptance or rollback depends on a broker.
    ``event_type`` is one row of the studio's own vocabulary
    (``studio.application.events``), never composed at the call site;
    ``subject`` is the document's name; ``data`` carries identity and the
    commit pointer, never a document's body (section 5).
    """

    def publish(self, *, event_type: str, subject: str, data: dict[str, object]) -> None:
        """State the fact. Never tells the caller whether it was delivered."""
        ...
