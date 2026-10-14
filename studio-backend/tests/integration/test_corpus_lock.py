"""One lock over the working tree, and writes off the event loop.

INT-SYNC-005: one process-wide lock spans a write's whole transaction (edit,
validation, commit), a push, a refresh, the poll and the install bundle's read,
so two concurrent writes produce two commits, each holding only its author's
change. INT-MCP-006: write handlers and write tools run on worker threads, so the
health check answers within its probe timeout while a long validation runs.
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent

from studio.adapters.inbound.http.app import create_app
from studio.adapters.outbound.git_cli.cli_git_sync import CliGitSync
from studio.container import Container
from studio.domain.model.validation_report import ValidationReport
from tests.conftest import FakeGitSync
from tests.people import (
    ADMIN,
    OWNER,
    WRITER,
    Server,
    bearer,
    configure_proxy_mode,
    shelve,
    signed_in,
)

# The kubelet's probe timeout is one second.
_PROBE_TIMEOUT = 1.0


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class SlowValidator:
    """A validation that takes a while, and notes how many ran at once."""

    def __init__(self, seconds: float, events: list[str] | None = None) -> None:
        self._seconds = seconds
        self._lock = threading.Lock()
        self._running = 0
        self.most_at_once = 0
        self.started = threading.Event()
        self.events = events if events is not None else []

    def validate(self) -> ValidationReport:
        with self._lock:
            self._running += 1
            self.most_at_once = max(self.most_at_once, self._running)
        self.events.append("validate")
        self.started.set()
        time.sleep(self._seconds)
        self.events.append("validated")
        with self._lock:
            self._running -= 1
        return ValidationReport(
            tests_passed=True, links_ok=True, tests_output="slow", links_output="slow"
        )


class OrderedGit(FakeGitSync):
    """A git fake that writes what it does into the validator's timeline."""

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self._events = events

    def commit_all(self, *, message, author) -> None:
        super().commit_all(message=message, author=author)
        self._events.append("commit")

    def pull(self) -> None:
        super().pull()
        self._events.append("pull")


def _git(cwd: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", *argv], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def _bumped(root: Path, rel: str, line: str) -> dict[str, str]:
    return {"raw": (root / rel).read_text(encoding="utf-8").rstrip("\n") + f"\n\n{line}\n"}


@intent("INT-SYNC-005")
def test_two_concurrent_writes_make_two_commits_each_holding_one_change(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    _git(root, "init", "--initial-branch=main", ".")
    _git(root, "config", "user.name", "seed")
    _git(root, "config", "user.email", "seed@test")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "seed")
    git = CliGitSync(root)
    git.ensure_ready()
    validator = SlowValidator(0.6)
    container = Container(
        playbook_root=root,
        validator=validator,
        runtime_skills_dir=root / "_runtime",
        git_sync=git,
    )
    writes = [
        ("/api/skills/do-alpha", "galaxies/craft/skills/do-alpha/SKILL.md", OWNER),
        ("/api/agents/alpha-agent", "galaxies/craft/agents/alpha-agent.md", WRITER),
    ]
    answers: dict[str, int] = {}
    with Server(create_app(container)) as srv:

        def write(path: str, rel: str, who: str) -> None:
            with httpx.Client(timeout=30) as http:
                res = http.put(
                    f"{srv.base_url}{path}",
                    json=_bumped(root, rel, f"By {who}."),
                    headers=signed_in(who),
                )
            answers[who] = res.status_code

        threads = [threading.Thread(target=write, args=w) for w in writes]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

    assert answers == {OWNER: 200, WRITER: 200}
    assert validator.most_at_once == 1, "two validations ran over one tree at once"
    for rel, who in ((w[1], w[2]) for w in writes):
        line = _git(root, "log", "-1", "--format=%ae|%ce", "--", rel).strip()
        assert line == f"{who}|playbook-studio@localhost", rel
        sha = _git(root, "log", "-1", "--format=%H", "--", rel).strip()
        touched = _git(root, "show", "--name-only", "--format=", sha).split()
        assert touched == [rel], f"{who}'s commit holds {touched}"
    assert len(_git(root, "log", "--format=%H").split()) == 3


@intent("INT-SYNC-005")
def test_the_poll_and_the_bundle_wait_for_a_write_in_flight(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    events: list[str] = []
    validator = SlowValidator(0.5, events)
    container = Container(
        playbook_root=root,
        validator=validator,
        runtime_skills_dir=root / "_runtime",
        git_sync=OrderedGit(events),
    )
    client = TestClient(create_app(container), client=("127.0.0.1", 50000))
    writer = threading.Thread(
        target=lambda: client.put(
            "/api/agents/alpha-agent",
            json=_bumped(root, "galaxies/craft/agents/alpha-agent.md", "By the writer."),
            headers=signed_in(WRITER),
        )
    )
    writer.start()
    assert validator.started.wait(5)
    poll = threading.Thread(
        target=lambda: container.refresh_content().execute(actor=container.service)
    )
    bundle = threading.Thread(
        target=lambda: events.append(
            "bundle:" + container.get_install_bundle().execute(runtime="claude-code").runtime
        )
    )
    poll.start()
    bundle.start()
    for t in (writer, poll, bundle):
        t.join(timeout=30)
    assert events[:3] == ["validate", "validated", "commit"], events
    assert sorted(events[3:]) == ["bundle:claude-code", "pull"], events


@intent("INT-MCP-006")
@pytest.mark.anyio
async def test_the_health_check_answers_while_a_long_validation_runs(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gated write through either door holds a worker thread, never the event loop."""
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    validator = SlowValidator(3.0)
    container = Container(
        playbook_root=root,
        validator=validator,
        runtime_skills_dir=root / "_runtime",
        git_sync=FakeGitSync(),
    )
    app = create_app(container)
    skill = "galaxies/craft/skills/do-alpha/SKILL.md"

    async def health_while_validating(base_url: str) -> None:
        with anyio.fail_after(10):
            while not validator.started.is_set():
                await anyio.sleep(0.05)
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as probe:
            started = time.monotonic()
            res = await probe.get(f"{base_url}/api/health")
        assert res.status_code == 200
        assert time.monotonic() - started < _PROBE_TIMEOUT

    with Server(app) as srv:
        # The machine door: a write tool over a personal token.
        async with (
            httpx.AsyncClient(headers=bearer(app, ADMIN), timeout=30) as http,
            streamable_http_client(f"{srv.base_url}/mcp", http_client=http) as (r, w, _),
            ClientSession(r, w) as session,
            anyio.create_task_group() as tasks,
        ):
            await session.initialize()
            tasks.start_soon(
                session.call_tool,
                "update_skill_document",
                {"name": "do-alpha", **_bumped(root, skill, "Over MCP.")},
            )
            await health_while_validating(srv.base_url)

        # The human door: a write route.
        validator.started.clear()
        async with (
            httpx.AsyncClient(timeout=30) as http,
            anyio.create_task_group() as tasks,
        ):
            tasks.start_soon(
                lambda: http.put(
                    f"{srv.base_url}/api/skills/do-alpha",
                    json=_bumped(root, skill, "Over HTTP."),
                    headers=signed_in(ADMIN),
                )
            )
            await health_while_validating(srv.base_url)
