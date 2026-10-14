"""Who a request acts as, on each door (INT-AUTH-008).

The OIDC sidecar's forwarded identity names a person only when the TCP peer is
loopback and the path is not the machine door; from anywhere else, or on /mcp,
the same headers act as nobody. A write with nobody behind it answers 401.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent

from tests.conftest import FakeGitSync
from tests.people import (
    ADMIN,
    OWNER,
    OWNERS_TEXT,
    READER,
    WRITER,
    Server,
    app_for,
    basic,
    configure_proxy_mode,
    proxied,
    shelve,
    sidecar_client,
    signed_in,
)

_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _skill_edit(root: Path) -> dict[str, str]:
    path = root / "galaxies/craft/skills/do-alpha/SKILL.md"
    return {"raw": path.read_text(encoding="utf-8") + "\nEdited.\n"}


@intent("INT-AUTH-008")
def test_the_sidecar_names_the_person(playbook_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    me = client.get("/api/me", headers=signed_in(WRITER, "wanda"))
    assert me.status_code == 200
    assert me.json() == {
        "name": "wanda",
        "email": WRITER,
        "service": False,
        "role": "galaxy writer",
        "galaxies": ["craft"],
        "atoms": [],
        "can_edit_playbook": False,
        "can_administer": False,
        "can_validate": True,
        "tokens": True,
    }
    owner = client.get("/api/me", headers=signed_in(OWNER)).json()
    assert owner["name"] == OWNER, "the name falls back to the email"
    assert owner["atoms"] == ["galaxies/craft/skills/do-alpha", "galaxies/craft/mcps/alpha-door.md"]
    assert client.get("/api/me", headers=signed_in(READER)).json()["role"] == "reader"
    admin = client.get("/api/me", headers=signed_in(ADMIN)).json()
    assert admin["galaxies"] == ["craft", "maker"] and admin["can_administer"]

    wanda = signed_in(WRITER, "wanda")
    res = client.put("/api/skills/do-alpha", json=_skill_edit(root), headers=wanda)
    assert res.status_code == 200
    assert (git.authors[-1].name, git.authors[-1].email) == ("wanda", WRITER)


@intent("INT-AUTH-008")
@pytest.mark.parametrize("peer", ["10.42.0.17", "192.168.1.5", "testclient"])
def test_forged_headers_from_any_other_peer_act_as_nobody(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch, peer: str
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = TestClient(app_for(root, git), client=(peer, 50000))
    forged = signed_in(ADMIN)
    assert client.get("/api/me", headers=forged).status_code == 401
    assert client.get("/api/skills/do-alpha", headers=forged).json()["can_edit"] is False
    res = client.put("/api/skills/do-alpha", json=_skill_edit(root), headers=forged)
    assert res.status_code == 401
    assert git.commits == []


@intent("INT-AUTH-008")
@pytest.mark.parametrize(
    "headers",
    [
        [("X-Forwarded-Email", ADMIN), ("X-Forwarded-Email", READER)],
        [("X-Forwarded-Email", "not-an-email")],
        [("X-Forwarded-Email", ADMIN), ("X-Forwarded-Preferred-Username", "Eve <eve@x>")],
        [("X-Forwarded-Preferred-Username", "admin")],
    ],
    ids=["two-emails", "not-an-email", "name-breaks-the-author-line", "no-email"],
)
def test_a_malformed_forwarded_identity_acts_as_nobody(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch, headers: list[tuple[str, str]]
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    client = sidecar_client(app_for(root, FakeGitSync()))
    proof = list(proxied().items())
    assert client.get("/api/me", headers=httpx.Headers(proof + headers)).status_code == 401


@intent("INT-AUTH-008")
@pytest.mark.parametrize(
    ("configured", "sent"),
    [("p" * 48, None), ("p" * 48, "q" * 48), ("", "p" * 48)],
    ids=["no-proxy-proof", "wrong-proxy-proof", "no-secret-configured"],
)
def test_without_the_proxy_secret_the_headers_name_nobody(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch, configured: str, sent: str | None
) -> None:
    """Another process in the pod reaches the app from loopback too: only the
    sidecar holds the secret it sends beside the forwarded identity."""
    configure_proxy_mode(monkeypatch)
    monkeypatch.setenv("STUDIO_PROXY_SECRET", configured)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    headers = {"X-Forwarded-Email": ADMIN}
    if sent is not None:
        headers.update(proxied(ADMIN, sent))
    assert client.get("/api/me", headers=headers).status_code == 401
    assert client.put("/api/owners", json={"raw": OWNERS_TEXT}, headers=headers).status_code == 401
    assert git.commits == []


@intent("INT-AUTH-008")
def test_a_write_without_a_trusted_identity_answers_401(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reads stay open behind the proxy; a write with nobody behind it is refused."""
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    assert client.get("/api/skills/do-alpha").status_code == 200
    for method, path, body in (
        ("PUT", "/api/skills/do-alpha", _skill_edit(root)),
        ("POST", "/api/validate", None),
        ("POST", "/api/tokens", None),
        ("PUT", "/api/owners", {"raw": "/ a@b.c\n"}),
    ):
        assert client.request(method, path, json=body).status_code == 401, path
    assert git.commits == []


@intent("INT-AUTH-008")
@pytest.mark.anyio
async def test_forwarded_headers_are_ignored_on_the_machine_door(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On /mcp the proxy passes client headers through, so they name nobody: the
    shared credential still acts as the service, and without one the door is shut."""
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    app = app_for(root, git)
    forged = signed_in(ADMIN, "admin")
    with Server(app) as srv:
        async with httpx.AsyncClient(headers=forged) as anonymous:
            shut = await anonymous.post(f"{srv.base_url}/mcp/", json={})
        async with (
            httpx.AsyncClient(headers={**forged, **basic()}) as http,
            streamable_http_client(f"{srv.base_url}/mcp", http_client=http) as (r, w, _),
            ClientSession(r, w) as session,
        ):
            await session.initialize()
            me = await session.call_tool("get_me", {})
            result = await session.call_tool(
                "update_skill_document", {"name": "do-alpha", **_skill_edit(root)}
            )
    assert shut.status_code == 401
    assert not result.isError
    assert json.loads(me.content[0].text)["service"] is True
    assert git.authors[-1].service and git.authors[-1].email != ADMIN


@intent("INT-AUTH-008")
def test_standing_alone_the_basic_holder_acts_as_the_service(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the proxy, the Basic gate covers the human door and its holder is the
    service: today's behaviour, with every write allowed and signed as the service."""
    configure_proxy_mode(monkeypatch)
    monkeypatch.setenv("STUDIO_AUTH_SCOPE", "all")
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = TestClient(app_for(root, git))
    me = client.get("/api/me", headers={**signed_in(READER), **basic()})
    assert me.status_code == 200
    assert me.json()["service"] is True and me.json()["role"] == "admin"
    assert me.json()["tokens"] is False
    res = client.put("/api/skills/do-alpha", json=_skill_edit(root), headers=basic())
    assert res.status_code == 200
    assert git.authors[-1].service


@intent("INT-AUTH-008")
def test_the_server_keeps_the_real_peer() -> None:
    """uvicorn would otherwise rewrite the peer from X-Forwarded-For, and any client
    could claim to be the sidecar."""
    dockerfile = (_ROOT / "devops/Dockerfile").read_text(encoding="utf-8")
    cmd = dockerfile[dockerfile.rindex("CMD [") :]
    assert '"--no-proxy-headers"' in cmd
    run = (_ROOT / "studio-backend/studio/adapters/inbound/http/run.py").read_text(
        encoding="utf-8"
    )
    assert re.search(r"proxy_headers=False", run)


@intent("INT-AUTH-008")
def test_the_chart_hands_the_proxy_its_secret() -> None:
    """The sidecar sends the secret only if the chart gives it one and tells it to."""
    chart = (_ROOT / "k8s/templates/deployment.yaml").read_text(encoding="utf-8")
    proxy = chart[chart.index("- name: oauth2-proxy") :]
    assert "- --pass-basic-auth=true" in proxy
    assert "- --pass-user-headers=true" in proxy
    env = proxy[proxy.index("OAUTH2_PROXY_BASIC_AUTH_PASSWORD") :]
    assert "name: {{ .Values.auth.existingSecret }}" in env.split("- name:")[0]
    assert "key: STUDIO_PROXY_SECRET" in env.split("- name:")[0]

