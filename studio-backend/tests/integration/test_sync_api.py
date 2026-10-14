"""Sync integration tests: commit-per-gated-edit and the push/refresh flow."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest_intent import intent

from studio.adapters.inbound.http.app import create_app
from studio.container import Container
from tests.conftest import FakeGitSync, StubValidator


def _client_with(playbook_root: Path, git: FakeGitSync, ok: bool = True) -> TestClient:
    container = Container(
        playbook_root=playbook_root,
        validator=StubValidator(ok=ok),
        runtime_skills_dir=playbook_root / "_runtime",
        git_sync=git,
    )
    return TestClient(create_app(container))


class TestCommitPerGatedEdit:
    @intent("INT-SYNC-001")
    def test_passing_edit_becomes_a_commit(self, client: TestClient, fake_git: FakeGitSync) -> None:
        resp = client.put(
            "/api/refs/REF-Alpha/sections/1",
            json={"body": "Always be Alpha, twice. See `REF-Beta.md`."},
        )
        assert resp.status_code == 200
        assert fake_git.commits == ["docs(REF-Alpha): edit section 1"]

    @intent("INT-SYNC-001")
    def test_rejected_edit_creates_no_commit(
        self, failing_client: TestClient, fake_git: FakeGitSync
    ) -> None:
        resp = failing_client.put(
            "/api/refs/REF-Alpha/sections/1",
            json={"body": "This edit must not survive."},
        )
        assert resp.status_code == 422
        assert fake_git.commits == []

    @intent("INT-SYNC-001")
    def test_rejected_edit_restores_the_file_byte_for_byte(
        self, failing_client: TestClient, playbook_root: Path
    ) -> None:
        # A rejected edit must be a perfect no-op. This body injects its own
        # section heading; rolling back through write_ref_section() used to stop
        # at the injected heading and leave a duplicated section behind,
        # corrupting the working clone and jamming git pull --rebase. The raw
        # restore must return the file to its exact original bytes.
        ref_path = playbook_root / "REF-Alpha.md"
        original = ref_path.read_text(encoding="utf-8")
        resp = failing_client.put(
            "/api/refs/REF-Alpha/sections/1",
            json={"body": "## 1. Rules\n\nInjected duplicate heading. See `REF-Beta.md`."},
        )
        assert resp.status_code == 422
        assert ref_path.read_text(encoding="utf-8") == original

    @intent("INT-SYNC-001")
    def test_scaffolding_a_ref_becomes_a_commit(
        self, client: TestClient, fake_git: FakeGitSync
    ) -> None:
        resp = client.post(
            "/api/refs",
            json={
                "name": "REF-Gamma",
                "domain": "practice",
                "title": "Gamma",
                "summary": "Gamma things.",
            },
        )
        assert resp.status_code == 201
        assert fake_git.commits == ["feat(ref): REF-Gamma"]


class TestPushFlow:
    def test_status_reports_unpushed_commits(
        self, client: TestClient, fake_git: FakeGitSync
    ) -> None:
        client.put(
            "/api/refs/REF-Alpha/sections/1",
            json={"body": "Always be Alpha, twice. See `REF-Beta.md`."},
        )
        resp = client.get("/api/sync/status")
        assert resp.status_code == 200
        assert resp.json()["unpushed_commits"] == 1

    def test_push_publishes(self, client: TestClient, fake_git: FakeGitSync) -> None:
        resp = client.post("/api/sync/push")
        assert resp.status_code == 200
        assert fake_git.pushes == 1
        assert fake_git.pulls == 0

    @intent("INT-SYNC-002")
    def test_rejected_push_reconciles_and_retries(self, playbook_root: Path) -> None:
        git = FakeGitSync(reject_pushes=1)
        client = _client_with(playbook_root, git)
        resp = client.post("/api/sync/push")
        assert resp.status_code == 200
        assert git.pulls == 1
        assert git.pushes == 1

    @intent("INT-SYNC-002")
    def test_conflict_surfaces_as_409_with_files(self, playbook_root: Path) -> None:
        git = FakeGitSync(reject_pushes=1, conflict_files=["REF-Alpha.md", "intent.yaml"])
        client = _client_with(playbook_root, git)
        resp = client.post("/api/sync/push")
        assert resp.status_code == 409
        assert resp.json()["error"] == "SyncConflictError"
        assert "REF-Alpha.md" in resp.json()["detail"]

    def test_refresh_pulls_upstream(self, client: TestClient, fake_git: FakeGitSync) -> None:
        resp = client.post("/api/sync/refresh")
        assert resp.status_code == 200
        assert fake_git.pulls == 1


class TestLocalComposition:
    def test_local_run_has_no_sync_surface(self, playbook_root: Path) -> None:
        container = Container(
            playbook_root=playbook_root,
            validator=StubValidator(ok=True),
            runtime_skills_dir=playbook_root / "_runtime",
        )
        client = TestClient(create_app(container))
        assert client.get("/api/health").json()["sync"] is False
        assert client.get("/api/sync/status").status_code == 404

    def test_managed_composition_reports_sync_capability(self, client: TestClient) -> None:
        assert client.get("/api/health").json()["sync"] is True
