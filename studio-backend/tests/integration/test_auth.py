"""Auth-gate tests: fail-closed HTTP Basic across /api and the /mcp mount.

Attest the INT-AUTH claims in the repo intent.yaml. `/openapi.json` stands in
for "any gated route": the middleware runs before routing, so requests are
rejected or admitted purely by the gate, independent of business endpoints.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest_intent import intent

from studio.adapters.inbound.http.app import create_app
from studio.adapters.inbound.http.download_tokens import DownloadTokens
from studio.container import Container
from tests.conftest import FakeGitSync, StubValidator


def _build_client(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path, **env: str
) -> TestClient:
    """A TestClient over a freshly built app with the given auth env (others cleared)."""
    for key in (
        "STUDIO_AUTH_USER",
        "STUDIO_AUTH_PASSWORD",
        "STUDIO_AUTH_DISABLED",
        "STUDIO_AUTH_SCOPE",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    container = Container(
        playbook_root=playbook_root,
        validator=StubValidator(ok=True),
        runtime_skills_dir=playbook_root / "_runtime",
        git_sync=FakeGitSync(),
    )
    return TestClient(create_app(container))


def _basic(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@intent("INT-AUTH-001")
def test_rejects_without_credentials(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """INT-AUTH-001: configured auth refuses unauthenticated requests on every surface."""
    client = _build_client(
        monkeypatch, playbook_root, STUDIO_AUTH_USER="ops", STUDIO_AUTH_PASSWORD="s3cret"
    )
    api = client.get("/openapi.json")
    assert api.status_code == 401
    assert api.headers.get("WWW-Authenticate", "").lower().startswith("basic")
    assert client.post("/mcp", json={}).status_code == 401


@intent("INT-AUTH-002")
def test_accepts_valid_credentials(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """INT-AUTH-002: valid credentials are admitted; a wrong password is refused."""
    client = _build_client(
        monkeypatch, playbook_root, STUDIO_AUTH_USER="ops", STUDIO_AUTH_PASSWORD="s3cret"
    )
    assert client.get("/openapi.json", headers=_basic("ops", "s3cret")).status_code == 200
    assert client.get("/openapi.json", headers=_basic("ops", "nope")).status_code == 401


@intent("INT-AUTH-003")
def test_health_is_exempt(monkeypatch: pytest.MonkeyPatch, playbook_root: Path) -> None:
    """INT-AUTH-003: the health endpoint answers without credentials (for probes)."""
    client = _build_client(
        monkeypatch, playbook_root, STUDIO_AUTH_USER="ops", STUDIO_AUTH_PASSWORD="s3cret"
    )
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@intent("INT-AUTH-004")
def test_fails_closed_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """INT-AUTH-004: no credentials and not explicitly disabled -> 503, not open."""
    client = _build_client(monkeypatch, playbook_root)
    assert client.get("/openapi.json").status_code == 503
    assert client.post("/mcp", json={}).status_code == 503
    # Health still answers so probes keep working.
    assert client.get("/api/health").status_code == 200


@intent("INT-AUTH-005")
def test_mcp_scope_gates_only_the_machine_door(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """INT-AUTH-005: scope=mcp keeps /mcp Basic-gated while the human surfaces
    serve open for an OIDC reverse proxy in front to gate."""
    client = _build_client(
        monkeypatch,
        playbook_root,
        STUDIO_AUTH_USER="ops",
        STUDIO_AUTH_PASSWORD="s3cret",
        STUDIO_AUTH_SCOPE="mcp",
    )
    # Enter the app lifespan so the /mcp transport's session manager is running;
    # the gate decision (before routing) is what these assertions exercise.
    with client:
        # The /mcp machine door stays gated: no credential is refused, a valid one admitted.
        assert client.post("/mcp", json={}).status_code == 401
        admitted = client.post("/mcp", json={}, headers=_basic("ops", "s3cret"))
        assert admitted.status_code not in (401, 503)
        # The human surfaces serve open; oauth2-proxy is their gate in front.
        assert client.get("/openapi.json").status_code == 200


@intent("INT-AUTH-005")
def test_mcp_scope_fails_closed_on_the_machine_door(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """INT-AUTH-005: scope=mcp with no credentials fails the /mcp door closed
    (503) while the human surfaces stay open for the proxy."""
    client = _build_client(monkeypatch, playbook_root, STUDIO_AUTH_SCOPE="mcp")
    assert client.post("/mcp", json={}).status_code == 503
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_agent_credential_returns_the_basic_pair_to_the_service(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """/api/agent-credential hands the stand-alone connect menu the base64 HTTP
    Basic pair its caller already holds; behind oauth2-proxy (scope=mcp) a signed-in
    person is refused it, because the shared credential is the service's."""
    standalone = _build_client(
        monkeypatch, playbook_root, STUDIO_AUTH_USER="ops", STUDIO_AUTH_PASSWORD="s3cret"
    )
    res = standalone.get("/api/agent-credential", headers=_basic("ops", "s3cret"))
    assert res.status_code == 200
    assert base64.b64decode(res.json()["credential"]).decode() == "ops:s3cret"

    proxied = _build_client(
        monkeypatch,
        playbook_root,
        STUDIO_AUTH_USER="ops",
        STUDIO_AUTH_PASSWORD="s3cret",
        STUDIO_AUTH_SCOPE="mcp",
    )
    proxied = TestClient(proxied.app, client=("127.0.0.1", 50000))
    person = {"X-Forwarded-Email": "ana@example.com"}
    assert proxied.get("/api/agent-credential", headers=person).status_code == 403
    assert proxied.get("/api/agent-credential").status_code == 403


def test_agent_credential_fails_closed_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """With no credential configured there is nothing to hand out: 503, never an
    empty or bogus credential."""
    client = _build_client(monkeypatch, playbook_root, STUDIO_AUTH_DISABLED="true")
    assert client.get("/api/agent-credential").status_code == 503


def _install_paths(token: str) -> list[str]:
    return [
        f"/mcp/install/{token}/install.sh?runtime=claude-code",
        f"/mcp/install/{token}/install.ps1?runtime=claude-code",
        f"/mcp/install/{token}/bundle.tar.gz?runtime=claude-code",
    ]


@intent("INT-AUTH-006")
@pytest.mark.parametrize("scope", ["all", "mcp"])
def test_a_download_token_admits_the_install_routes(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path, scope: str
) -> None:
    """INT-AUTH-006: a token the door minted admits a GET on the install routes
    without the Basic credential, in either scope; no token, or a forged one, is
    refused like any other unauthenticated request."""
    client = _build_client(
        monkeypatch,
        playbook_root,
        STUDIO_AUTH_USER="ops",
        STUDIO_AUTH_PASSWORD="s3cret",
        STUDIO_AUTH_SCOPE=scope,
    )
    token = client.app.state.download_tokens.mint()
    for path in _install_paths(token):
        assert client.get(path).status_code == 200, path
    expires, _, signature = token.partition(".")
    for forged in (
        "",
        "not-a-token",
        f"{int(expires) + 3600}.{signature}",
        f"{expires}.x",
        f"{expires}.%C3%A9",
        f"{expires}.{signature[:-1]}%C3%A9",
    ):
        for path in _install_paths(forged or "-"):
            assert client.get(path).status_code == 401, path


@intent("INT-AUTH-006")
def test_a_download_token_admits_nothing_else(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """INT-AUTH-006: the token is download-only. It opens no MCP call, no REST
    route, and no other method on the install routes."""
    client = _build_client(
        monkeypatch, playbook_root, STUDIO_AUTH_USER="ops", STUDIO_AUTH_PASSWORD="s3cret"
    )
    token = client.app.state.download_tokens.mint()
    with client:
        assert client.post("/mcp", json={}, params={"token": token}).status_code == 401
        assert client.post(f"/mcp/install/{token}/", json={}).status_code == 401
        assert client.post(_install_paths(token)[2]).status_code == 401
        assert client.get(f"/api/graph?token={token}").status_code == 401
        assert client.get(f"/mcp/install/{token}").status_code == 401


@intent("INT-AUTH-006")
def test_a_download_token_does_not_open_an_unconfigured_door(
    monkeypatch: pytest.MonkeyPatch, playbook_root: Path
) -> None:
    """INT-AUTH-006 with INT-AUTH-004: with no credential configured the install
    routes fail closed like every gated route, token or not."""
    client = _build_client(monkeypatch, playbook_root, STUDIO_AUTH_SCOPE="mcp")
    token = client.app.state.download_tokens.mint()
    for path in _install_paths(token):
        assert client.get(path).status_code == 503, path


@intent("INT-AUTH-006")
def test_a_download_token_expires_and_belongs_to_its_minter() -> None:
    """INT-AUTH-006: a token stops working at its expiry, and another process's
    token (another key) never verifies."""
    now = [1_000_000.0]
    tokens = DownloadTokens(ttl_seconds=600, clock=lambda: now[0])
    token = tokens.mint()
    assert tokens.verify(token)
    now[0] += 599
    assert tokens.verify(token)
    now[0] += 1
    assert not tokens.verify(token)
    assert not tokens.verify(DownloadTokens(clock=lambda: now[0]).mint())
