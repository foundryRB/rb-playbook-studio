"""Code the gates run cannot reach past its owner's rights (INT-GATE-006).

The playbook's suite runs code the corpus carries, skill scripts among it, and an
atom owner writes that code. The gates therefore judge a copy of the clone, the
code runs without the studio's settings in its environment, and in the deployed
image it runs as an unprivileged user who owns that copy and cannot enter the
clone, which the studio keeps to itself. An owner whose script rewrites OWNERS
during validation changes a copy that is thrown away.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest
from pytest_intent import intent

from studio.adapters.inbound.http.app import create_app
from studio.adapters.outbound.git_cli.cli_git_sync import CliGitSync
from studio.adapters.outbound.playbook_fs import subprocess_playbook_validator as gates
from studio.adapters.outbound.playbook_fs.subprocess_playbook_validator import (
    SubprocessPlaybookValidator,
)
from studio.container import Container
from tests.conftest import FakeGitSync
from tests.people import (
    OWNER,
    OWNERS_TEXT,
    configure_proxy_mode,
    shelve,
    sidecar_client,
    signed_in,
)

# The corpus's own suite: it runs each skill's check script, as a real suite runs
# the scripts skills carry, and holds the studio's settings out of reach.
_SUITE = """
import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_skill_check_runs():
    for check in sorted(ROOT.glob("galaxies/*/skills/*/check.py")):
        runpy.run_path(str(check))


def test_the_studio_settings_are_out_of_reach():
    assert not [k for k in os.environ if k.upper().startswith("STUDIO_")]
"""

# What an atom owner's script tries: make its owner an admin.
_GRAB = """
from pathlib import Path

root = Path(__file__).resolve().parents[4]
owners = root / "OWNERS"
owners.write_text(owners.read_text(encoding="utf-8") + "/ owner@example.com\\n", encoding="utf-8")
"""


@pytest.fixture
def corpus(playbook_root: Path) -> Path:
    root = shelve(playbook_root)
    (root / "tests").mkdir()
    (root / "tests" / "test_corpus.py").write_text(_SUITE, encoding="utf-8")
    (root / "scripts" / "check_links.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    return root


@intent("INT-GATE-006")
def test_an_owner_script_run_by_the_gates_cannot_grant_its_owner_more(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    git = FakeGitSync()
    container = Container(
        playbook_root=corpus,
        validator=SubprocessPlaybookValidator(corpus),
        runtime_skills_dir=corpus / "_runtime",
        git_sync=git,
    )
    client = sidecar_client(create_app(container))
    res = client.put(
        "/api/skills/do-alpha/files/check.py", json={"raw": _GRAB}, headers=signed_in(OWNER)
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"], "the gates ran the owner's script and the suite passed"
    assert (corpus / "OWNERS").read_text(encoding="utf-8") == OWNERS_TEXT
    assert client.get("/api/me", headers=signed_in(OWNER)).json()["role"] == "atom owner"
    assert git.authors[-1].email == OWNER
    assert not list(corpus.glob("**/.pytest_cache")), "the gates leave nothing in the clone"


@intent("INT-GATE-006")
def test_the_gates_run_without_the_studio_settings(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STUDIO_TOKEN_KEY", "k" * 48)
    monkeypatch.setenv("STUDIO_CONTENT_REPO_URL", "https://x-access-token:secret@example.com/a/b")
    report = SubprocessPlaybookValidator(corpus).validate()
    assert report.tests_passed, report.tests_output
    assert report.links_ok


class _GatesUser:
    pw_uid = 4242
    pw_gid = 4343


def _users(name: str) -> type[_GatesUser]:
    if name != "gates":
        raise KeyError(name)
    return _GatesUser


@intent("INT-GATE-006")
def test_the_gates_run_as_the_unprivileged_user_who_owns_the_copy(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a gates user named, every gate command runs as that user, without its
    own supplementary groups, at home in the scratch it owns; the copy is chowned
    to it, and whatever it left running is ended."""
    monkeypatch.setitem(sys.modules, "pwd", types.SimpleNamespace(getpwnam=_users))
    owned: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        gates.os,
        "chown",
        lambda path, uid, gid, **_: owned.append((str(path), uid, gid)),
        raising=False,
    )
    runs: list[dict] = []

    def run(argv, **kwargs):
        runs.append(kwargs)
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    monkeypatch.setattr(gates.subprocess, "run", run)
    reaped: list[int] = []
    monkeypatch.setattr(gates, "_reap", reaped.append)
    monkeypatch.setenv("STUDIO_TOKEN_KEY", "k" * 48)

    assert SubprocessPlaybookValidator(corpus, run_as="gates").validate().ok
    assert len(runs) == 2
    for kwargs in runs:
        assert (kwargs["user"], kwargs["group"], kwargs["extra_groups"]) == (4242, 4343, [])
        home = Path(kwargs["env"]["HOME"])
        assert Path(kwargs["cwd"]) == home / "playbook"
        assert kwargs["env"]["USER"] == "gates"
        assert not [k for k in kwargs["env"] if k.upper().startswith("STUDIO_")]
    assert owned and {(uid, gid) for _, uid, gid in owned} == {(4242, 4343)}
    copied = {Path(p).relative_to(home).as_posix() for p, _, _ in owned if Path(p) != home}
    assert "playbook/OWNERS" in copied and "playbook/tests/test_corpus.py" in copied
    assert not [p for p in copied if p.startswith("playbook/.git")]
    assert reaped == [4242]


@intent("INT-GATE-006")
def test_an_unknown_gates_user_refuses_rather_than_running_as_the_studio(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "pwd", types.SimpleNamespace(getpwnam=_users))
    monkeypatch.setattr(
        gates.subprocess, "run", lambda *a, **k: pytest.fail("ran the corpus's code")
    )
    report = SubprocessPlaybookValidator(corpus, run_as="nobody-here").validate()
    assert not report.ok and "nobody-here" in report.tests_output


@intent("INT-GATE-006")
def test_the_image_names_an_unprivileged_gates_user() -> None:
    dockerfile = (Path(__file__).resolve().parents[3] / "devops/Dockerfile").read_text(
        encoding="utf-8"
    )
    runtime = dockerfile[dockerfile.rindex("FROM ") :]
    assert re.search(r"useradd --system [^\n]*\bgates\b", runtime)
    assert re.search(r"STUDIO_GATES_USER=gates", runtime)


@intent("INT-GATE-006")
@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_the_clone_is_closed_to_every_other_user(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()
    subprocess.run(["git", "init", "-q", str(clone)], check=True)
    CliGitSync(clone).ensure_ready()
    assert clone.stat().st_mode & 0o777 == 0o700
