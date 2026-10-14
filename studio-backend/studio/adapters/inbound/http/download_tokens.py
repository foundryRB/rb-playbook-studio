"""Short-lived, download-only credentials for the toolchain install routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable

__all__ = ["DOWNLOAD_PREFIX", "DownloadTokens"]

#: The install routes. They sit under /mcp because that is the path machine
#: credentials reach (the OIDC proxy skips it); the token is the first segment.
DOWNLOAD_PREFIX = "/mcp/install/"

_DEFAULT_TTL_SECONDS = 600
_PURPOSE = b"playbook-studio install download\0"


class DownloadTokens:
    """Mints and checks the tokens a returned install command carries.

    A connector holds the studio's Basic credential; the shell that runs an
    install command does not, and the command lands in a transcript. So the door
    never hands that credential out: get_install_command mints a token that
    admits only GETs on the install routes and expires in minutes, and that is
    all the command carries. The signing key is random per process and never
    leaves it, so a restart retires every outstanding token, and none can be
    forged or stretched.
    """

    def __init__(
        self,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._key = secrets.token_bytes(32)
        self._clock = clock
        self.ttl_seconds = ttl_seconds

    def mint(self) -> str:
        """A token valid for ttl_seconds from now."""
        expires = int(self._clock()) + self.ttl_seconds
        return f"{expires}.{self._sign(expires)}"

    def verify(self, token: str) -> bool:
        """Whether the token was minted here and has not expired."""
        expires_text, _, signature = token.partition(".")
        if not (expires_text.isascii() and expires_text.isdigit()) or len(expires_text) > 12:
            return False
        expires = int(expires_text)
        # Bytes, not str: a path can carry any text, and compare_digest refuses a
        # str holding non-ASCII characters rather than comparing it.
        if not hmac.compare_digest(
            signature.encode("utf-8", "replace"), self._sign(expires).encode("ascii")
        ):
            return False
        return self._clock() < expires

    def _sign(self, expires: int) -> str:
        digest = hmac.new(self._key, _PURPOSE + str(expires).encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
