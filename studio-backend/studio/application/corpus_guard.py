"""The rights check and the corpus lock every write passes through.

One working tree serves every door: HTTP writes run on worker threads, MCP write
tools run on worker threads, and the content poll pulls on its own. A commit
names one person as its author, so it must hold exactly that person's change:
one process-wide re-entrant lock spans a write's whole transaction (edit,
validation, commit), a push, a refresh and the poll, and the install bundle
reads under it for a consistent snapshot.

Rights come from OWNERS in the corpus the studio serves, read again whenever its
text changes, so a merged or pulled OWNERS takes effect on the next request. A
file that does not parse grants nothing: every person reads, nobody writes,
until it is fixed (fail closed, the same as no file at all).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.exceptions.forbidden_error import ForbiddenError
from studio.domain.exceptions.invalid_owners_error import InvalidOwnersError
from studio.domain.exceptions.not_authenticated_error import NotAuthenticatedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action, Owners
from studio.logging import get_logger

__all__ = ["CorpusGuard"]

logger = get_logger(__name__)

#: One lock per process: the working tree is one, whichever door writes to it.
_CORPUS_LOCK = threading.RLock()


class CorpusGuard:
    """Decides `may(actor, action, path)` from OWNERS and serialises the corpus."""

    def __init__(self, repository: PlaybookRepository, lock: threading.RLock | None = None) -> None:
        self._repository = repository
        self._lock = lock or _CORPUS_LOCK
        self._cached: tuple[str | None, Owners] | None = None

    def owners(self) -> Owners:
        """The rights of the corpus as it stands now."""
        text = self._repository.read_owners()
        cached = self._cached
        if cached is not None and cached[0] == text:
            return cached[1]
        owners = Owners()
        if text is not None:
            try:
                owners = Owners.parse(text)
            except InvalidOwnersError as exc:
                logger.error("OWNERS does not parse, so nobody writes until it does: %s", exc)
        self._cached = (text, owners)
        return owners

    def may(self, actor: Actor | None, action: Action, path: str = "") -> bool:
        return self.owners().may(actor, action, path)

    def require(self, actor: Actor | None, action: Action, path: str = "") -> Actor:
        """Return the actor when OWNERS allows the act; raise naming the role otherwise."""
        if actor is None:
            raise NotAuthenticatedError()
        owners = self.owners()
        if not owners.may(actor, action, path):
            logger.info("Refused %s %s for %s", action, path or "/", actor.email)
            raise ForbiddenError(owners.refusal(actor, action, path))
        return actor

    @contextmanager
    def write(self, actor: Actor | None, action: Action, path: str = "") -> Iterator[Actor]:
        """Hold the corpus for one write transaction by an actor allowed to make it.

        The check runs before waiting, so a refused write never queues behind a
        long validation, and again under the lock, so an OWNERS change that
        landed while it waited is the one that decides.
        """
        self.require(actor, action, path)
        with self._lock:
            yield self.require(actor, action, path)

    @contextmanager
    def held(self) -> Iterator[None]:
        """Hold the corpus without a rights check (the poll, a consistent read)."""
        with self._lock:
            yield
