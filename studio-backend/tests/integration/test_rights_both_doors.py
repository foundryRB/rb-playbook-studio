"""One table of cases drives both doors.

A reader writes nothing; an atom owner edits only what it owns; a galaxy writer
edits and creates only in its galaxy; an admin does everything; and every
refusal names the role the act needs. The human door is driven as the OIDC
sidecar drives it (a forwarded identity from loopback), the machine door with
each person's own personal token, and both answer from the one rights function.
Every write a person causes is a commit naming them as its author.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent

from tests.conftest import FakeGitSync
from tests.people import (
    ADMIN,
    DOOR_CARD,
    OWNER,
    OWNERS_TEXT,
    PEOPLE,
    READER,
    WRITER,
    Server,
    app_for,
    bearer,
    configure_proxy_mode,
    shelve,
    sidecar_client,
    signed_in,
)

_SKILL = "galaxies/craft/skills/do-alpha/SKILL.md"
_AGENT = "galaxies/craft/agents/alpha-agent.md"
_REF = "galaxies/craft/REF-Alpha.md"
_GALAXY = "galaxies/craft/GALAXY.md"
_CARD = "galaxies/craft/mcps/alpha-door.md"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _bumped(root: Path, rel: str, who: str) -> str:
    """The document with one more line, so every accepted write changes something."""
    text = (root / rel).read_text(encoding="utf-8")
    return text.rstrip("\n") + f"\n\nEdited by {who}.\n"


def _short(who: str) -> str:
    return who.split("@")[0]


Request = tuple[str, str, dict | None]
ToolCall = tuple[str, dict]


@dataclass(frozen=True)
class Case:
    id: str
    http: Callable[[Path, str], Request]
    tool: Callable[[Path, str], ToolCall]
    allowed: frozenset[str]
    needs: str
    commits: bool = True


def _create_skill(root: Path, who: str) -> dict:
    return {"name": f"new-{_short(who)}", "description": "Does new things.", "refs": ["REF-Beta"]}


def _create_agent(root: Path, who: str) -> dict:
    return {
        "name": f"maker-{_short(who)}",
        "title": "A maker agent",
        "description": "Makes things; hand it making.",
        "refs": ["REF-Beta"],
        "skills": ["do-alpha"],
        "galaxy": "maker",
    }


def _create_card(root: Path, who: str) -> dict:
    name = f"door-{_short(who)}"
    return {"kind": "mcp", "name": name, "galaxy": "craft", "raw": DOOR_CARD.format(name=name)}


CASES = [
    Case(
        "edit-an-owned-skill",
        lambda r, w: ("PUT", "/api/skills/do-alpha", {"raw": _bumped(r, _SKILL, w)}),
        lambda r, w: ("update_skill_document", {"name": "do-alpha", "raw": _bumped(r, _SKILL, w)}),
        frozenset({ADMIN, WRITER, OWNER}),
        "needs the owner of galaxies/craft/skills/do-alpha, a galaxy writer of craft, or an admin",
    ),
    Case(
        "edit-an-agent-nobody-owns-by-name",
        lambda r, w: ("PUT", "/api/agents/alpha-agent", {"raw": _bumped(r, _AGENT, w)}),
        lambda r, w: (
            "update_agent_document",
            {"name": "alpha-agent", "raw": _bumped(r, _AGENT, w)},
        ),
        frozenset({ADMIN, WRITER}),
        "needs the owner of galaxies/craft/agents/alpha-agent.md, a galaxy writer of craft",
    ),
    Case(
        "replace-a-ref",
        lambda r, w: ("PUT", "/api/refs/REF-Alpha", {"raw": _bumped(r, _REF, w)}),
        lambda r, w: ("update_ref_document", {"ref_name": "REF-Alpha", "raw": _bumped(r, _REF, w)}),
        frozenset({ADMIN, WRITER}),
        "editing galaxies/craft/REF-Alpha.md needs a galaxy writer of craft, or an admin",
    ),
    Case(
        "edit-a-ref-section",
        lambda r, w: ("PUT", "/api/refs/REF-Alpha/sections/1", {"body": f"By {w}."}),
        lambda r, w: (
            "update_ref_section",
            {"ref_name": "REF-Alpha", "number": 1, "body": f"By {w}."},
        ),
        frozenset({ADMIN, WRITER}),
        "needs a galaxy writer of craft, or an admin",
    ),
    Case(
        "replace-the-galaxy-page",
        lambda r, w: ("PUT", "/api/galaxies/craft", {"raw": _bumped(r, _GALAXY, w)}),
        lambda r, w: ("update_galaxy_document", {"name": "craft", "raw": _bumped(r, _GALAXY, w)}),
        frozenset({ADMIN, WRITER}),
        "editing galaxies/craft/GALAXY.md needs a galaxy writer of craft, or an admin",
    ),
    Case(
        "replace-the-playbook-page",
        lambda r, w: ("PUT", "/api/playbook", {"raw": _bumped(r, "AI-PLAYBOOK.md", w)}),
        lambda r, w: ("update_playbook_document", {"raw": _bumped(r, "AI-PLAYBOOK.md", w)}),
        frozenset({ADMIN}),
        "editing AI-PLAYBOOK.md needs the admin role",
    ),
    Case(
        "replace-an-owned-card",
        lambda r, w: ("PUT", "/api/doors/alpha-door", {"raw": _bumped(r, _CARD, w)}),
        lambda r, w: ("update_door_document", {"name": "alpha-door", "raw": _bumped(r, _CARD, w)}),
        frozenset({ADMIN, WRITER, OWNER}),
        "needs the owner of galaxies/craft/mcps/alpha-door.md, a galaxy writer of craft",
    ),
    Case(
        "create-a-skill-in-the-galaxy",
        lambda r, w: ("POST", "/api/skills", _create_skill(r, w)),
        lambda r, w: ("create_skill", _create_skill(r, w)),
        frozenset({ADMIN, WRITER}),
        "needs a galaxy writer of craft, or an admin",
    ),
    Case(
        "create-an-agent-in-another-galaxy",
        lambda r, w: ("POST", "/api/agents", _create_agent(r, w)),
        lambda r, w: ("create_agent", _create_agent(r, w)),
        frozenset({ADMIN}),
        "needs a galaxy writer of maker, or an admin",
    ),
    Case(
        "create-a-card-in-the-galaxy",
        lambda r, w: ("POST", "/api/doors", _create_card(r, w)),
        lambda r, w: ("create_door", _create_card(r, w)),
        frozenset({ADMIN, WRITER}),
        "needs a galaxy writer of craft, or an admin",
    ),
    Case(
        "replace-owners",
        lambda r, w: ("PUT", "/api/owners", {"raw": OWNERS_TEXT + f"# kept by {w}\n"}),
        lambda r, w: ("update_owners", {"raw": OWNERS_TEXT + f"# kept by {w}\n"}),
        frozenset({ADMIN}),
        "this needs the admin role",
    ),
    Case(
        "run-the-gates",
        lambda r, w: ("POST", "/api/validate", None),
        lambda r, w: ("run_validation", {}),
        frozenset({ADMIN, WRITER, OWNER}),
        "running the gates needs a role that writes",
        commits=False,
    ),
    Case(
        "push",
        lambda r, w: ("POST", "/api/sync/push", None),
        lambda r, w: ("push_changes", {}),
        frozenset({ADMIN}),
        "this needs the admin role",
        commits=False,
    ),
    Case(
        "refresh",
        lambda r, w: ("POST", "/api/sync/refresh", None),
        lambda r, w: ("refresh_content", {}),
        frozenset({ADMIN}),
        "this needs the admin role",
        commits=False,
    ),
]

_ROLE_OF = {ADMIN: "admin", WRITER: "galaxy writer", OWNER: "atom owner", READER: "reader"}


def _check(case: Case, who: str, ok: bool, text: str, git: FakeGitSync, before: int) -> None:
    if who in case.allowed:
        assert ok, f"{who} was refused {case.id}: {text}"
        if case.commits:
            assert len(git.commits) == before + 1, f"{case.id} by {who} made no commit"
            assert git.authors[-1].email == who and not git.authors[-1].service
    else:
        assert not ok, f"{who} was allowed {case.id}"
        assert case.needs in text, f"refusal of {case.id} for {who} does not name the role: {text}"
        assert f"you are a{'n' if who in (ADMIN, OWNER) else ''} {_ROLE_OF[who]}" in text
        assert len(git.commits) == before


@intent("INT-AUTH-010", "INT-SYNC-004")
@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_the_human_door_answers_the_table(
    case: Case, playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    for who in PEOPLE:
        method, path, body = case.http(root, who)
        before = len(git.commits)
        res = client.request(method, path, json=body, headers=signed_in(who))
        ok = res.status_code in (200, 201)
        assert ok or res.status_code == 403, (who, case.id, res.status_code, res.text)
        _check(case, who, ok, res.text, git, before)


@intent("INT-AUTH-010", "INT-SYNC-004")
@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
async def test_the_machine_door_answers_the_table(
    case: Case, playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    app = app_for(root, git)
    with Server(app) as srv:
        for who in PEOPLE:
            tool, args = case.tool(root, who)
            before = len(git.commits)
            async with (
                httpx.AsyncClient(headers=bearer(app, who)) as http,
                streamable_http_client(f"{srv.base_url}/mcp", http_client=http) as (r, w, _),
                ClientSession(r, w) as session,
            ):
                await session.initialize()
                result = await session.call_tool(tool, args)
            _check(case, who, not result.isError, str(result.content), git, before)


@intent("INT-AUTH-010")
def test_reads_carry_can_edit_from_the_same_rights(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every atom read answers `can_edit` for the reader from the rights the write asks."""
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    client = sidecar_client(app_for(root, FakeGitSync()))
    reads = {
        "/api/skills/do-alpha": {ADMIN, WRITER, OWNER},
        "/api/agents/alpha-agent": {ADMIN, WRITER},
        "/api/doors/alpha-door": {ADMIN, WRITER, OWNER},
        "/api/refs/REF-Alpha": {ADMIN, WRITER},
        "/api/galaxies/craft": {ADMIN, WRITER},
        "/api/playbook": {ADMIN},
    }
    for path, editors in reads.items():
        for who in PEOPLE:
            res = client.get(path, headers=signed_in(who))
            assert res.status_code == 200, (path, who)
            assert res.json()["can_edit"] is (who in editors), (path, who)
        # Nobody signed in reads and edits nothing.
        assert client.get(path).json()["can_edit"] is False
