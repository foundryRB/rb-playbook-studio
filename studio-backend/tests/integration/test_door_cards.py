"""MCP and RAG cards are atoms like agent documents (INT-GATE-005).

Readable, editable and creatable through both doors, gated like every edit: an
accepted write is one commit, a refused one restores the card (or its absence).
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent

from tests.conftest import FakeGitSync
from tests.people import (
    DOOR_CARD,
    WRITER,
    Server,
    app_for,
    bearer,
    configure_proxy_mode,
    shelve,
    sidecar_client,
    signed_in,
)

_CARD = "galaxies/craft/mcps/alpha-door.md"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@intent("INT-GATE-005")
def test_a_card_is_read_edited_and_created_over_http(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    who = signed_in(WRITER)

    card = client.get("/api/doors/alpha-door", headers=who).json()
    assert (card["kind"], card["galaxy"], card["can_edit"]) == ("mcp", "craft", True)
    edited = card["raw"].replace("The door to alpha.", "The door to alpha, revised.")
    assert client.put("/api/doors/alpha-door", json={"raw": edited}, headers=who).status_code == 200
    assert "revised" in (root / _CARD).read_text(encoding="utf-8")
    assert git.commits[-1] == "docs(mcp): replace alpha-door.md"

    rag = {
        "kind": "rag",
        "name": "alpha-seat",
        "galaxy": "craft",
        "raw": DOOR_CARD.format(name="alpha-seat"),
    }
    created = client.post("/api/doors", json=rag, headers=who)
    assert created.status_code == 201
    assert created.json()["kind"] == "rag"
    assert (root / "galaxies/craft/rags/alpha-seat.md").is_file()
    assert git.commits[-1] == "feat(rag): alpha-seat"
    assert client.get("/api/doors/alpha-seat").json()["name"] == "alpha-seat"


@intent("INT-GATE-005")
@pytest.mark.parametrize(
    "body",
    [
        {"kind": "tool", "name": "x-door", "galaxy": "craft", "raw": "x"},
        {"kind": "mcp", "name": "Not_Kebab", "galaxy": "craft", "raw": "x"},
        {"kind": "mcp", "name": "x-door", "galaxy": "craft", "raw": DOOR_CARD.format(name="y")},
    ],
    ids=["unknown-kind", "bad-name", "frontmatter-names-another-card"],
)
def test_a_card_that_does_not_fit_is_refused_before_anything_is_written(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch, body: dict
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    assert client.post("/api/doors", json=body, headers=signed_in(WRITER)).status_code == 400
    renamed = DOOR_CARD.format(name="renamed-door")
    res = client.put("/api/doors/alpha-door", json={"raw": renamed}, headers=signed_in(WRITER))
    assert res.status_code == 400
    assert not list((root / "galaxies/craft/mcps").glob("x-door*"))
    assert (root / _CARD).read_text(encoding="utf-8") == DOOR_CARD.format(name="alpha-door")
    assert git.commits == []


@intent("INT-GATE-005", "INT-MCP-001")
@pytest.mark.anyio
async def test_a_refused_card_write_restores_the_card_on_either_door(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    app = app_for(root, git, ok=False)
    original = (root / _CARD).read_text(encoding="utf-8")
    edited = original + "\nMust not survive.\n"
    res = sidecar_client(app).put(
        "/api/doors/alpha-door", json={"raw": edited}, headers=signed_in(WRITER)
    )
    assert res.status_code == 422
    with Server(app) as srv:
        async with (
            httpx.AsyncClient(headers=bearer(app, WRITER)) as http,
            streamable_http_client(f"{srv.base_url}/mcp", http_client=http) as (r, w, _),
            ClientSession(r, w) as session,
        ):
            await session.initialize()
            update = await session.call_tool(
                "update_door_document", {"name": "alpha-door", "raw": edited}
            )
            create = await session.call_tool(
                "create_door",
                {
                    "kind": "mcp",
                    "name": "beta-door",
                    "galaxy": "craft",
                    "raw": DOOR_CARD.format(name="beta-door"),
                },
            )
    assert update.isError and "rejected by the validation gates" in str(update.content)
    assert create.isError and "rejected by the validation gates" in str(create.content)
    assert (root / _CARD).read_text(encoding="utf-8") == original
    assert not (root / "galaxies/craft/mcps/beta-door.md").exists()
    assert git.commits == []
