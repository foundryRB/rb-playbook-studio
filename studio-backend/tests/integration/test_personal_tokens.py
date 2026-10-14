"""Personal tokens: a person's own credential for the machine door (INT-AUTH-009).

A signed-in person mints their own; it acts as that person and nobody else, an
expired or revoked one is refused, and the key comes from the deployment's
Secret, so a token outlives the process that minted it.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent

from studio.adapters.inbound.http.personal_tokens import PersonalTokens, _b64, _unb64
from studio.domain.model.actor import Actor
from tests.conftest import FakeGitSync
from tests.people import (
    ADMIN,
    OWNERS_TEXT,
    READER,
    WRITER,
    Server,
    app_for,
    basic,
    configure_proxy_mode,
    shelve,
    sidecar_client,
    signed_in,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _call(base_url: str, token: str, tool: str, args: dict) -> tuple[bool, str]:
    """Call one tool with a personal token; (ok, text)."""
    headers = {"Authorization": f"Bearer {token}"}
    async with (
        httpx.AsyncClient(headers=headers) as http,
        streamable_http_client(f"{base_url}/mcp", http_client=http) as (r, w, _),
        ClientSession(r, w) as session,
    ):
        await session.initialize()
        result = await session.call_tool(tool, args)
    return not result.isError, str(result.content[0].text if result.content else "")


async def _status(base_url: str, token: str) -> int:
    """The gate's answer to a bare MCP request carrying this token."""
    async with httpx.AsyncClient() as http:
        res = await http.post(
            f"{base_url}/mcp/", json={}, headers={"Authorization": f"Bearer {token}"}
        )
    return res.status_code


@intent("INT-AUTH-009")
@pytest.mark.anyio
async def test_a_minted_token_acts_as_its_person_on_the_machine_door(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    app = app_for(root, git)
    minted = sidecar_client(app).post("/api/tokens", headers=signed_in(WRITER, "wanda"))
    assert minted.status_code == 201
    body = minted.json()
    assert (body["email"], body["name"]) == (WRITER, "wanda")
    assert body["expires_at"].endswith("Z")
    skill = root / "galaxies/craft/skills/do-alpha/SKILL.md"
    with Server(app) as srv:
        ok, me = await _call(srv.base_url, body["token"], "get_me", {})
        assert ok and json.loads(me)["email"] == WRITER
        assert json.loads(me)["role"] == "galaxy writer"
        ok, _ = await _call(
            srv.base_url,
            body["token"],
            "update_skill_document",
            {"name": "do-alpha", "raw": skill.read_text(encoding="utf-8") + "\nBy token.\n"},
        )
    assert ok
    assert (git.authors[-1].name, git.authors[-1].email) == ("wanda", WRITER)


@intent("INT-AUTH-009")
def test_only_a_signed_in_person_mints_one(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    proxied = sidecar_client(app_for(root, FakeGitSync()))
    assert proxied.post("/api/tokens", headers=signed_in(READER)).status_code == 201
    assert proxied.post("/api/tokens").status_code == 401

    monkeypatch.setenv("STUDIO_AUTH_SCOPE", "all")
    standalone = TestClient(app_for(root, FakeGitSync()))
    refused = standalone.post("/api/tokens", headers=basic())
    assert refused.status_code == 403 and "for people" in refused.json()["detail"]

    monkeypatch.setenv("STUDIO_AUTH_SCOPE", "mcp")
    monkeypatch.delenv("STUDIO_TOKEN_KEY")
    keyless = sidecar_client(app_for(root, FakeGitSync()))
    assert keyless.post("/api/tokens", headers=signed_in(READER)).status_code == 503
    assert keyless.get("/api/me", headers=signed_in(READER)).json()["tokens"] is False


@intent("INT-AUTH-009")
@pytest.mark.anyio
async def test_a_token_names_only_its_person_and_survives_a_restart(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A token signed by the Secret's key verifies in a fresh process; one signed by
    another key, or one whose named person was swapped, does not."""
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    first = app_for(root, FakeGitSync())
    token = sidecar_client(first).post("/api/tokens", headers=signed_in(READER)).json()["token"]

    prefix, payload, signature = token.split(".")
    claims = json.loads(_unb64(payload))
    claims["e"] = ADMIN
    swapped = ".".join([prefix, _b64(json.dumps(claims).encode()), signature])
    other_key = PersonalTokens(b"z" * 48).mint(Actor(name="admin", email=ADMIN))[0]

    restarted = app_for(root, FakeGitSync())
    with Server(restarted) as srv:
        ok, me = await _call(srv.base_url, token, "get_me", {})
        assert ok and json.loads(me)["email"] == READER
        assert await _status(srv.base_url, swapped) == 401
        assert await _status(srv.base_url, other_key) == 401
        assert await _status(srv.base_url, "pst1.garbage") == 401
    # A personal token opens the machine door only: the stand-alone human door wants Basic.
    monkeypatch.setenv("STUDIO_AUTH_SCOPE", "all")
    standalone = TestClient(app_for(root, FakeGitSync()))
    as_bearer = {"Authorization": f"Bearer {token}"}
    assert standalone.get("/api/me", headers=as_bearer).status_code == 401


@intent("INT-AUTH-009")
def test_a_token_expires() -> None:
    now = [1_000_000.0]
    tokens = PersonalTokens(b"k" * 48, ttl_seconds=3600, clock=lambda: now[0])
    token, claims = tokens.mint(Actor(name="ana", email="ana@example.com"))
    assert claims.expires_at == 1_000_000 + 3600
    assert tokens.verify(token) == claims
    now[0] += 3599
    assert tokens.verify(token) is not None
    now[0] += 1
    assert tokens.verify(token) is None
    assert PersonalTokens(b"short").enabled is False


@intent("INT-AUTH-009")
@pytest.mark.anyio
async def test_a_not_before_line_in_owners_revokes_earlier_tokens(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The admin's revocation takes effect on the next request, with no restart, and
    spares the tokens issued after it."""
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    app = app_for(root, FakeGitSync())
    early = sidecar_client(app).post("/api/tokens", headers=signed_in(WRITER)).json()["token"]
    with Server(app) as srv:
        assert (await _call(srv.base_url, early, "get_me", {}))[0]
        (root / "OWNERS").write_text(
            OWNERS_TEXT + f"not-before {WRITER} 2999-01-01\n", encoding="utf-8"
        )
        assert await _status(srv.base_url, early) == 401
        (root / "OWNERS").write_text(
            OWNERS_TEXT + f"not-before {WRITER} 2000-01-01T00:00:00Z\n", encoding="utf-8"
        )
        assert (await _call(srv.base_url, early, "get_me", {}))[0]
