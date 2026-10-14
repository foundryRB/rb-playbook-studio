"""INT-EVENTS-001: publishing is one-way. With the bus unreachable, every mutation
completes with the same outcome, the same response, and the same corpus on disk as it
does with the bus up (accepted and committed, or refused and rolled back), each dropped
publish is logged, and every fact is one row of the studio's own events page."""

from __future__ import annotations

import json
import logging
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest_intent import intent

from studio.adapters.inbound.http.app import create_app
from studio.adapters.outbound.events.publisher import SOURCE, LoggingEventPublisher, cloud_event
from studio.application import events as vocabulary
from studio.application.events import (
    AGENT_CREATED,
    AGENT_UPDATED,
    CHANGES_PUSHED,
    DOOR_CREATED,
    DOOR_UPDATED,
    GALAXY_UPDATED,
    OWNERS_UPDATED,
    PLAYBOOK_UPDATED,
    REF_CREATED,
    REF_UPDATED,
    SKILL_CREATED,
    SKILL_UPDATED,
    VALIDATION_FAILED,
    state_fact,
)
from studio.container import Container
from tests.conftest import FakeGitSync, StubValidator


@contextmanager
def captured_warnings():
    """Collect the studio's own warnings: its logger namespace does not propagate, so
    a handler on that namespace is how a test sees them."""
    records: list[logging.LogRecord] = []

    class Sink(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    sink = Sink(level=logging.WARNING)
    logger = logging.getLogger("studio")
    logger.addHandler(sink)
    try:
        yield records
    finally:
        logger.removeHandler(sink)


class RecordingPublisher:
    """A bus that is up. It builds the real envelope before recording, so a payload
    the adapter could not serialize fails here instead of being dropped in production."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict]] = []

    def publish(self, *, event_type, subject, data) -> None:
        cloud_event(event_type=event_type, subject=subject, data=data)
        self.published.append((event_type, subject, data))

    @property
    def types(self) -> list[str]:
        return [t for t, _s, _d in self.published]


class RaisingPublisher:
    """A bus that is down in the least forgiving way: every publish explodes."""

    def __init__(self) -> None:
        self.attempts: list[str] = []

    def publish(self, *, event_type, subject, data) -> None:
        self.attempts.append(event_type)
        raise ConnectionError("bus unreachable")


def _client(root: Path, events, ok: bool = True) -> TestClient:
    container = Container(
        playbook_root=root,
        validator=StubValidator(ok=ok),
        runtime_skills_dir=root / "_runtime",
        git_sync=FakeGitSync(),
        events=events,
    )
    return TestClient(create_app(container))


def _tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file() and "_runtime" not in p.parts
    }


REF = {"name": "REF-Gamma", "domain": "practice", "title": "Gamma", "summary": "Gamma practices."}
SKILL = {"name": "do-beta", "description": "Does beta things.", "refs": ["REF-Beta"]}
AGENT = {
    "name": "beta-agent",
    "title": "The beta agent",
    "description": "Does the beta work; hand it beta.",
    "refs": ["REF-Beta"],
    "skills": ["do-alpha"],
}


CARD = {
    "kind": "mcp",
    "name": "beta-door",
    "galaxy": "craft",
    "raw": "---\nname: beta-door\ngalaxy: craft\nrefs:\n  - REF-Beta\n---\n\n# MCP: beta-door\n",
}


def _file_and_replace_a_card(client: TestClient):
    client.post("/api/doors", json=CARD)
    return _rewrite(client, "/api/doors/beta-door", "# MCP: beta-door", "# MCP: beta-door, v2")


def _rewrite(client: TestClient, path: str, needle: str, replacement: str):
    original = client.get(path).json()["raw"]
    return client.put(path, json={"raw": original.replace(needle, replacement)})


# Each mutation: the request, and the facts it states when the gates pass.
_ACTS = [
    pytest.param(lambda c: c.post("/api/refs", json=REF), [REF_CREATED], id="create-ref"),
    pytest.param(lambda c: c.post("/api/skills", json=SKILL), [SKILL_CREATED], id="create-skill"),
    pytest.param(lambda c: c.post("/api/agents", json=AGENT), [AGENT_CREATED], id="create-agent"),
    pytest.param(
        lambda c: c.put("/api/refs/REF-Alpha/sections/1", json={"body": "Revised guidance.\n"}),
        [REF_UPDATED],
        id="edit-section",
    ),
    pytest.param(
        lambda c: _rewrite(c, "/api/refs/REF-Beta", "Guidance", "Guidance (revised)"),
        [REF_UPDATED],
        id="replace-ref",
    ),
    pytest.param(
        lambda c: _rewrite(c, "/api/skills/do-alpha", "Does alpha", "Does alpha, calmly"),
        [SKILL_UPDATED],
        id="replace-skill",
    ),
    pytest.param(
        lambda c: _rewrite(c, "/api/agents/alpha-agent", "end to end", "end to end, calmly"),
        [AGENT_UPDATED],
        id="replace-agent",
    ),
    pytest.param(
        lambda c: _rewrite(c, "/api/playbook", "# AI Playbook", "# AI Playbook (revised)"),
        [PLAYBOOK_UPDATED],
        id="replace-playbook",
    ),
    pytest.param(
        lambda c: _rewrite(c, "/api/galaxies/craft", "Do not duplicate", "Do not repeat"),
        [GALAXY_UPDATED],
        id="replace-galaxy",
    ),
    pytest.param(
        _file_and_replace_a_card, [DOOR_CREATED, DOOR_UPDATED], id="create-and-replace-card"
    ),
    pytest.param(
        lambda c: c.put("/api/owners", json={"raw": "/ admin@example.com\n"}),
        [OWNERS_UPDATED],
        id="replace-owners",
    ),
    pytest.param(lambda c: c.post("/api/sync/push"), [CHANGES_PUSHED], id="push"),
]


def _two_roots(playbook_root: Path, tmp_path_factory) -> tuple[Path, Path]:
    """Two independent copies of the synthetic corpus, outside the fixture's own
    directory (playbook_root is tmp_path itself, so a copy inside it would nest)."""
    base = tmp_path_factory.mktemp("bus")
    up, down = base / "up", base / "down"
    shutil.copytree(playbook_root, up)
    shutil.copytree(playbook_root, down)
    return up, down


@intent("INT-EVENTS-001")
@pytest.mark.parametrize(("act", "facts"), _ACTS)
def test_every_accepted_mutation_is_identical_with_the_bus_down(
    playbook_root: Path, tmp_path_factory, act, facts
) -> None:
    up_root, down_root = _two_roots(playbook_root, tmp_path_factory)

    up = RecordingPublisher()
    response_up = act(_client(up_root, up))
    assert response_up.status_code < 300, response_up.text
    assert up.types == facts
    for _t, subject, data in up.published:
        assert subject
        assert json.dumps(data)
        assert "raw" not in data and "body" not in data  # pointers, never the document

    down = RaisingPublisher()
    with captured_warnings() as warnings:
        response_down = act(_client(down_root, down))
    assert down.attempts == facts, "the act must still attempt each publish"
    assert response_down.status_code == response_up.status_code
    assert response_down.json() == response_up.json()
    assert _tree(up_root) == _tree(down_root)
    for fact in facts:
        assert any(fact in r.getMessage() for r in warnings), f"a dropped {fact} must be logged"


@intent("INT-EVENTS-001")
def test_a_refused_mutation_states_the_gate_and_rolls_back_the_same_either_way(
    playbook_root: Path, tmp_path_factory
) -> None:
    """A gate's refusal is the fact a routine watches for corpus health; the edit is
    rolled back byte-identical whether or not the bus heard about it."""
    up_root, down_root = _two_roots(playbook_root, tmp_path_factory)
    before = _tree(up_root)

    up = RecordingPublisher()
    broken = {"raw": "# REF: Broken\n"}
    response_up = _client(up_root, up, ok=False).put("/api/refs/REF-Beta", json=broken)
    assert response_up.status_code == 422
    assert up.types == [VALIDATION_FAILED]
    data = up.published[0][2]
    assert data["kind"] == "ref" and data["target"] == "REF-Beta"
    assert data["gates"] == ["tests", "links"]
    assert _tree(up_root) == before

    down = RaisingPublisher()
    with captured_warnings() as warnings:
        response_down = _client(down_root, down, ok=False).put("/api/refs/REF-Beta", json=broken)
    assert down.attempts == [VALIDATION_FAILED]
    assert response_down.status_code == 422 and response_down.json() == response_up.json()
    assert _tree(down_root) == before
    assert any(VALIDATION_FAILED in r.getMessage() for r in warnings)


@intent("INT-EVENTS-001")
def test_state_fact_never_raises_and_no_publisher_states_nothing():
    with captured_warnings() as warnings:
        state_fact(RaisingPublisher(), event_type=REF_UPDATED, subject="REF-Alpha", data={})
    assert any(REF_UPDATED in r.getMessage() for r in warnings)
    state_fact(None, event_type=REF_UPDATED, subject="REF-Alpha", data={})


@intent("INT-EVENTS-001")
def test_the_envelope_is_a_cloudevent_carrying_pointers_not_payloads():
    raw = cloud_event(event_type=REF_UPDATED, subject="REF-Alpha", data={"ref": "REF-Alpha"})
    event = json.loads(raw)
    assert event["specversion"] == "1.0"
    assert event["type"] == REF_UPDATED
    assert event["subject"] == "REF-Alpha"
    assert event["source"] == SOURCE
    assert event["datacontenttype"] == "application/json"
    assert event["id"] and event["time"]
    other = json.loads(cloud_event(event_type=REF_UPDATED, subject="REF-Alpha", data={}))
    assert other["id"] != event["id"]
    with pytest.raises(TypeError):
        cloud_event(event_type=REF_UPDATED, subject="x", data={"doc": object()})
    LoggingEventPublisher().publish(event_type=REF_UPDATED, subject="x", data={"doc": object()})


_EVENTS_PAGE = Path(__file__).resolve().parents[3] / "docs/src/content/docs/architecture/events.md"


@intent("INT-EVENTS-001")
def test_the_events_page_states_exactly_the_types_the_studio_emits():
    """REF-Events section 3: each owner states its own types on its own page, held
    against the publisher by its own tests."""
    emitted = {
        value
        for name, value in vars(vocabulary).items()
        if name.isupper() and isinstance(value, str) and value.startswith("com.foundry.")
    }
    assert emitted
    assert {v.split(".")[2] for v in emitted} == {"playbook"}
    page = _EVENTS_PAGE.read_text(encoding="utf-8")
    stated = set(re.findall(r"^\| `(com\.foundry\.[a-z.]+)` \|", page, flags=re.M))
    assert stated == emitted, (
        f"page states {sorted(stated - emitted)} the studio never emits; "
        f"studio emits {sorted(emitted - stated)} the page never states"
    )
