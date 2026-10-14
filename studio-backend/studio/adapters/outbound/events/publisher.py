"""Publish this studio's facts to the shared event bus, one way and never blocking.

REF-Events fixes the envelope (CloudEvents) and the rule (section 6: a publish
never blocks, slows, or fails the act that caused it). Both are built here rather
than taken from a shared package: the REF is the only shared artifact and every
producer owns its own outbound adapter (section 7). The shape is small enough to
own: an envelope, a serializer, and a fire-and-forget send.

``publish`` builds the envelope, puts it on a **bounded** queue, and returns. A
daemon worker thread owns the NATS connection and drains the queue. A full queue
drops the oldest fact and logs, because the REF forbids queueing into unbounded
memory and a bus is not the record of what happened anyway. The connection is
made lazily on the worker thread, so an unreachable broker costs one background
reconnect loop and no startup path, and ``nats-py`` is imported inside the
worker, so a studio with no bus grant never touches the import.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import queue
import threading
import uuid
from datetime import datetime, timezone

from studio.logging import get_logger

__all__ = [
    "SOURCE",
    "LoggingEventPublisher",
    "NatsEventPublisher",
    "cloud_event",
    "resolve_event_publisher",
]

logger = get_logger(__name__)

#: This studio as one stable URI-reference, fixed for its lifetime. A consumer
#: checks provenance against it, so it does not track the hostname an install
#: happens to serve the studio on.
SOURCE = "/foundry/playbook-studio"

_QUEUE_DEPTH = 256
_RECONNECT_SECONDS = 30.0


def cloud_event(*, event_type: str, subject: str, data: dict[str, object]) -> bytes:
    """One CloudEvent, JSON-encoded, ready to publish.

    ``id`` is unique per event because delivery is at-least-once and it is the
    consumer's dedupe key. ``time`` is when the fact became true, which is now:
    the publish happens after the act it describes has already committed. A
    ``data`` the encoder refuses raises here, before anything is queued.
    """
    return json.dumps(
        {
            "specversion": "1.0",
            "id": str(uuid.uuid4()),
            "source": SOURCE,
            "type": event_type,
            "subject": subject,
            "time": datetime.now(timezone.utc).isoformat(),
            "datacontenttype": "application/json",
            "data": data,
        },
        separators=(",", ":"),
    ).encode("utf-8")


class LoggingEventPublisher:
    """The publisher a studio with no bus grant runs: states each fact to the log.

    Every act completes exactly as it would with a broker up, which is the
    one-way rule rather than a fallback. The envelope is still built, so a
    payload the bus would refuse is caught on the install that has no bus.
    """

    def publish(self, *, event_type: str, subject: str, data: dict[str, object]) -> None:
        try:
            cloud_event(event_type=event_type, subject=subject, data=data)
        except (TypeError, ValueError) as exc:
            logger.warning("dropped event %s: could not build envelope (%s)", event_type, exc)
            return
        logger.info("event %s %s %s", event_type, subject, json.dumps(data, default=str))


class NatsEventPublisher:
    """Implements EventPublisher over NATS, delivering on a background thread."""

    def __init__(self, *, servers: str, creds_path: str | None = None) -> None:
        self._servers = servers
        self._creds_path = creds_path
        self._queue: queue.Queue[tuple[str, bytes]] = queue.Queue(maxsize=_QUEUE_DEPTH)
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()

    def publish(self, *, event_type: str, subject: str, data: dict[str, object]) -> None:
        """State the fact and return. Never raises, never waits on delivery."""
        try:
            payload = cloud_event(event_type=event_type, subject=subject, data=data)
        except (TypeError, ValueError) as exc:
            logger.warning("dropped event %s: could not build envelope (%s)", event_type, exc)
            return
        self._ensure_worker()
        try:
            self._queue.put_nowait((event_type, payload))
        except queue.Full:
            with contextlib.suppress(queue.Empty):
                self._queue.get_nowait()  # drop the oldest, keep the newest
            logger.warning(
                "event queue full (depth %d); dropped an older fact to admit %s",
                _QUEUE_DEPTH,
                event_type,
            )
            with contextlib.suppress(queue.Full):
                self._queue.put_nowait((event_type, payload))

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._run, name="event-publisher", daemon=True)
            self._worker.start()

    def _run(self) -> None:
        try:
            asyncio.run(self._drain())
        except Exception as exc:  # noqa: BLE001 - a dead worker must never escape
            logger.warning("event publisher worker stopped: %s", exc)

    async def _drain(self) -> None:
        try:
            import nats
        except ImportError:  # pragma: no cover - only when the dependency is absent
            logger.warning("nats-py is not installed; events will not be published")
            return
        connection = None
        loop = asyncio.get_running_loop()
        while True:
            event_type, payload = await loop.run_in_executor(None, self._queue.get)
            if connection is None or not connection.is_connected:
                try:
                    connection = await nats.connect(
                        servers=[s.strip() for s in self._servers.split(",") if s.strip()],
                        user_credentials=self._creds_path or None,
                        max_reconnect_attempts=-1,
                        reconnect_time_wait=_RECONNECT_SECONDS,
                    )
                except Exception as exc:  # noqa: BLE001 - the bus may simply be down
                    logger.warning("dropped event %s: bus unreachable (%s)", event_type, exc)
                    continue
            try:
                # The subject IS the type, so a consumer's wildcard filter is the
                # type hierarchy itself.
                await connection.publish(event_type, payload)
            except Exception as exc:  # noqa: BLE001 - never surfaced to a caller
                logger.warning("dropped event %s: publish failed (%s)", event_type, exc)


def resolve_event_publisher() -> LoggingEventPublisher | NatsEventPublisher:
    """The publisher this install is configured for, or the logging one.

    ``STUDIO_NATS_SERVERS`` names the bus the studio's grant reached; unset
    means no grant, and the studio states its facts to the log.
    ``STUDIO_NATS_CREDS`` is the credentials file the chart assembles from
    the two halves the grant produced (the seed this studio minted, the JWT the
    platform signed).
    """
    servers = os.environ.get("STUDIO_NATS_SERVERS", "").strip()
    if not servers:
        return LoggingEventPublisher()
    return NatsEventPublisher(
        servers=servers, creds_path=os.environ.get("STUDIO_NATS_CREDS") or None
    )
