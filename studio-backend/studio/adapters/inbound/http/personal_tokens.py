"""Personal tokens: a person's own credential for the machine door.

A signed-in person mints one from the Connect menu and sets it as a Bearer
header in any MCP client; the door then acts as that person, with their rights
and their name on every commit. A token names the person and an expiry and is
signed with a key from the app's Secret, so it survives a restart and no
process can forge or stretch one. An admin revokes the tokens a person was
issued before a date by recording a `not-before` line for them in OWNERS; the
gate reads that line, this module only proves who minted what and when.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from studio.domain.model.actor import Actor
from studio.domain.model.rights import valid_email
from studio.logging import get_logger

__all__ = ["PersonalClaims", "PersonalTokens"]

logger = get_logger(__name__)

_KEY_ENV = "STUDIO_TOKEN_KEY"
_TTL_ENV = "STUDIO_TOKEN_TTL_DAYS"
_DEFAULT_TTL_DAYS = 90
_MIN_KEY_BYTES = 32
_PREFIX = "pst1"
_PURPOSE = b"playbook-studio personal token\0"
# A token whose issue time is ahead of this process's clock by more than this is
# refused: no honest mint lies about the future.
_SKEW_SECONDS = 300


@dataclass(frozen=True)
class PersonalClaims:
    """What a verified token states: whose it is, and when it was issued and ends."""

    email: str
    name: str
    issued_at: int
    expires_at: int

    def actor(self) -> Actor:
        return Actor(name=self.name, email=self.email)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class PersonalTokens:
    """Mints and checks personal tokens with the key the deployment's Secret holds."""

    def __init__(
        self,
        key: bytes | None,
        ttl_seconds: int = _DEFAULT_TTL_DAYS * 86400,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._key = key if key and len(key) >= _MIN_KEY_BYTES else None
        self.ttl_seconds = ttl_seconds
        self._clock = clock

    @classmethod
    def from_env(cls) -> PersonalTokens:
        """$STUDIO_TOKEN_KEY signs (32 bytes or more); without it nobody mints and
        no token is admitted. $STUDIO_TOKEN_TTL_DAYS sets the lifetime (90)."""
        raw = os.environ.get(_KEY_ENV, "")
        key = raw.encode("utf-8") if raw else None
        if key is not None and len(key) < _MIN_KEY_BYTES:
            logger.error(
                "%s is shorter than %d bytes; personal tokens are off", _KEY_ENV, _MIN_KEY_BYTES
            )
        elif key is None:
            logger.warning("%s is not set; personal tokens are off", _KEY_ENV)
        days = int(os.environ.get(_TTL_ENV) or _DEFAULT_TTL_DAYS)
        return cls(key, ttl_seconds=days * 86400)

    @property
    def enabled(self) -> bool:
        return self._key is not None

    def mint(self, actor: Actor) -> tuple[str, PersonalClaims]:
        """A token for this person, valid for ttl_seconds from now, with its claims."""
        if self._key is None:
            raise RuntimeError("personal tokens are not configured")
        now = int(self._clock())
        claims = PersonalClaims(
            email=actor.email, name=actor.name, issued_at=now, expires_at=now + self.ttl_seconds
        )
        body = {"e": claims.email, "n": claims.name, "i": now, "x": claims.expires_at}
        payload = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        return f"{_PREFIX}.{payload}.{self._sign(payload)}", claims

    def verify(self, token: str) -> PersonalClaims | None:
        """The claims of a token minted here that has not expired, or None."""
        if self._key is None or not token.isascii():
            return None
        prefix, _, rest = token.partition(".")
        payload, _, signature = rest.partition(".")
        if prefix != _PREFIX or not payload or not signature:
            return None
        if not hmac.compare_digest(signature.encode("ascii"), self._sign(payload).encode("ascii")):
            return None
        try:
            data = json.loads(_unb64(payload))
            claims = PersonalClaims(
                email=str(data["e"]),
                name=str(data["n"]),
                issued_at=int(data["i"]),
                expires_at=int(data["x"]),
            )
        except (ValueError, KeyError, TypeError, binascii.Error):
            return None
        now = self._clock()
        if not valid_email(claims.email) or now >= claims.expires_at:
            return None
        if claims.issued_at > now + _SKEW_SECONDS:
            return None
        return claims

    def _sign(self, payload: str) -> str:
        assert self._key is not None
        digest = hmac.new(self._key, _PURPOSE + payload.encode("ascii"), hashlib.sha256).digest()
        return _b64(digest)
