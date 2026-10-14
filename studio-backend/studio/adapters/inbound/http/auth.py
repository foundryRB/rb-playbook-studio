"""The studio's gate: who may come in, and who each request acts as.

The studio manages a private content repo, so its credentials gate it
fail-closed: a misconfigured deployment is closed, never silently open. Two
doors, two ways in:

- The machine door (/mcp) admits the shared HTTP Basic credential, which acts
  as the service, or a person's own personal token (Bearer), which acts as that
  person. The install routes under /mcp/install/ also admit a download token in
  place of a credential (download_tokens.py).
- The human door (the SPA and /api) is fronted by an OIDC reverse proxy when
  STUDIO_AUTH_SCOPE=mcp. The proxy runs as a sidecar and reaches the app over
  loopback, and its forwarded identity (X-Forwarded-Email and
  X-Forwarded-Preferred-Username) names the person. Those headers are trusted
  only from a loopback peer carrying the proxy's secret (STUDIO_PROXY_SECRET,
  the password of the Basic header the sidecar sets), and never on /mcp:
  anywhere else they act as nobody. Standing alone (scope "all"), the Basic
  gate covers the human door too and the holder acts as the service.

Every request leaves the gate with `request.state.actor` set: the person, the
service, or None (nobody the studio trusts). Writes refuse None.
"""

from __future__ import annotations

import base64
import os
import re
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from studio.adapters.inbound.http.download_tokens import DOWNLOAD_PREFIX, DownloadTokens
from studio.adapters.inbound.http.personal_tokens import PersonalTokens
from studio.container import Container
from studio.domain.model.actor import Actor
from studio.domain.model.rights import valid_email
from studio.logging import get_logger

__all__ = ["forwarded_person", "install_auth"]

logger = get_logger(__name__)

# The health probe must answer without credentials so liveness/readiness work.
_EXEMPT_PATHS = frozenset({"/api/health"})
_MCP_PREFIX = "/mcp"
# The OIDC sidecar reaches the app on loopback; no other peer may name a person.
_LOOPBACK = frozenset({"127.0.0.1", "::1"})
_EMAIL_HEADER = "X-Forwarded-Email"
_NAME_HEADER = "X-Forwarded-Preferred-Username"
_SAFE_NAME = re.compile(r"^[^\x00-\x1f\x7f<>]{1,200}$")
_CHALLENGE = {"WWW-Authenticate": 'Basic realm="playbook-studio"'}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _auth_scope() -> str:
    """Which surfaces the Basic gate covers (STUDIO_AUTH_SCOPE).

    "all" (default): every surface (SPA, /api, /mcp), the stand-alone posture.
    "mcp": only the /mcp machine door, because an OIDC reverse proxy
    (oauth2-proxy) fronts the SPA and /api for humans, who cannot complete an
    interactive login on a machine-to-machine channel. The chart sets this only
    when that proxy is present, so the human surfaces are never truly open.
    """
    scope = (os.environ.get("STUDIO_AUTH_SCOPE") or "all").strip().lower()
    return scope if scope in {"all", "mcp"} else "all"


def _on_machine_door(path: str) -> bool:
    return path == _MCP_PREFIX or path.startswith(_MCP_PREFIX + "/")


def forwarded_person(request: Request, proxy_secret: str) -> Actor | None:
    """The person the OIDC sidecar forwards, or None.

    Trusted only when the request proves it came from the sidecar: the TCP peer
    is loopback (the server runs with --no-proxy-headers so the peer is the real
    one), the path is not the machine door, where the proxy passes client
    headers through untouched, and the request carries the proxy's own secret as
    the password of its Basic header, which the sidecar sets on every request it
    authenticates and no other process in the pod holds. With no secret
    configured, nobody is trusted. One email header, shaped like an email; the
    name falls back to it.
    """
    if not proxy_secret or _on_machine_door(request.url.path):
        return None
    peer = request.client.host if request.client else None
    if peer not in _LOOPBACK or not _carries_proxy_secret(request, proxy_secret):
        return None
    emails = request.headers.getlist(_EMAIL_HEADER)
    names = request.headers.getlist(_NAME_HEADER)
    if len(emails) != 1 or len(names) > 1:
        return None
    email = emails[0].strip()
    name = (names[0].strip() if names else "") or email
    if not valid_email(email) or not _SAFE_NAME.fullmatch(name):
        return None
    return Actor(name=name, email=email)


def install_auth(
    app: FastAPI,
    container: Container,
    download_tokens: DownloadTokens | None = None,
    personal_tokens: PersonalTokens | None = None,
) -> None:
    """Gate the studio's routes and resolve the actor of every request.

    Enforced when STUDIO_AUTH_USER and STUDIO_AUTH_PASSWORD are both set;
    turned off only by an explicit STUDIO_AUTH_DISABLED=true (local dev and
    tests), where every door acts as the service unless a person is named by a
    personal token or, behind the proxy, the forwarded identity. With neither
    set, gated routes answer 503. STUDIO_AUTH_SCOPE picks the covered surfaces
    (see _auth_scope); the health endpoint stays exempt so orchestration probes
    keep working.
    """
    user = os.environ.get("STUDIO_AUTH_USER", "")
    password = os.environ.get("STUDIO_AUTH_PASSWORD", "")
    disabled = _truthy(os.environ.get("STUDIO_AUTH_DISABLED"))
    scope = _auth_scope()
    configured = bool(user and password)
    # The OIDC sidecar's proof that it, and no other process, forwards a person.
    proxy_secret = os.environ.get("STUDIO_PROXY_SECRET", "")
    if scope == "mcp" and not proxy_secret:
        logger.error(
            "STUDIO_PROXY_SECRET is not set: no forwarded identity is trusted, "
            "so people read and nobody writes on the human door"
        )

    if disabled:
        logger.warning("studio auth is DISABLED; do not expose this instance publicly")
    elif configured:
        logger.info("studio auth is ENABLED (HTTP Basic, scope=%s)", scope)
    else:
        logger.error(
            "studio auth is NOT CONFIGURED: set STUDIO_AUTH_USER and STUDIO_AUTH_PASSWORD, "
            "or STUDIO_AUTH_DISABLED=true for local dev; gated routes answer 503 until then"
        )

    def _token_person(request: Request) -> Actor | None:
        """The person a live, unrevoked personal token names."""
        if personal_tokens is None:
            return None
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        claims = personal_tokens.verify(token.strip())
        if claims is None:
            return None
        not_before = container.rights().owners().tokens_not_before(claims.email)
        if not_before is not None and claims.issued_at < not_before.timestamp():
            logger.info("Refused a personal token revoked in OWNERS for %s", claims.email)
            return None
        return claims.actor()

    async def _machine_door(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if disabled:
            request.state.actor = _token_person(request) or container.service
            return await call_next(request)
        if not configured:
            return _unconfigured()
        if _is_authorized(request, user, password):
            request.state.actor = container.service
            return await call_next(request)
        person = _token_person(request)
        if person is not None:
            request.state.actor = person
            return await call_next(request)
        if _holds_download_token(request, download_tokens):
            return await call_next(request)
        return Response(status_code=401, headers=_CHALLENGE)

    async def _human_door(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if scope == "mcp":
            # The proxy in front is this door's gate; the app learns who passed it.
            request.state.actor = forwarded_person(request, proxy_secret)
            return await call_next(request)
        if disabled:
            request.state.actor = container.service
            return await call_next(request)
        if not configured:
            return _unconfigured()
        if _is_authorized(request, user, password):
            request.state.actor = container.service
            return await call_next(request)
        return Response(status_code=401, headers=_CHALLENGE)

    @app.middleware("http")
    async def _gate(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.actor = None
        path = request.url.path
        if path in _EXEMPT_PATHS:
            return await call_next(request)
        if _on_machine_door(path):
            return await _machine_door(request, call_next)
        return await _human_door(request, call_next)


def _carries_proxy_secret(request: Request, secret: str) -> bool:
    """Whether the Basic header's password is the proxy's secret (the user part is
    the proxy's to fill and is not read)."""
    scheme, _, encoded = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    _, separator, password = decoded.partition(":")
    return bool(separator) and secrets.compare_digest(
        password.encode("utf-8"), secret.encode("utf-8")
    )


def _unconfigured() -> Response:
    return JSONResponse(status_code=503, content={"detail": "authentication is not configured"})


def _is_authorized(request: Request, user: str, password: str) -> bool:
    """Constant-time check of an HTTP Basic Authorization header against the configured pair."""
    scheme, _, encoded = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    got_user, separator, got_password = decoded.partition(":")
    if not separator:
        return False
    user_ok = secrets.compare_digest(got_user, user)
    password_ok = secrets.compare_digest(got_password, password)
    return user_ok and password_ok


def _holds_download_token(request: Request, tokens: DownloadTokens | None) -> bool:
    """Whether a request is a GET on the install routes carrying a live download token.

    The token admits nothing else: not an MCP call, not /api, not a write.
    """
    path = request.url.path
    if tokens is None or request.method != "GET" or not path.startswith(DOWNLOAD_PREFIX):
        return False
    token, separator, _ = path[len(DOWNLOAD_PREFIX) :].partition("/")
    return bool(separator) and tokens.verify(token)
