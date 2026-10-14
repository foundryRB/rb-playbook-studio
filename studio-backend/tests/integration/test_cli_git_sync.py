"""CliGitSync integration tests against real temporary git repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest_intent import intent

from studio.adapters.outbound.git_cli.cli_git_sync import CliGitSync, slug_from_remote
from studio.domain.exceptions.sync_conflict_error import SyncConflictError
from studio.domain.exceptions.sync_rejected_error import SyncRejectedError
from studio.domain.model.actor import Actor

_SERVICE = Actor(name="playbook-studio", email="playbook-studio@localhost", service=True)


def _git(cwd: Path, *argv: str) -> str:
    proc = subprocess.run(
        ["git", *argv], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return proc.stdout


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """A bare origin seeded with one commit on main."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare", "--initial-branch=main", ".")
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", str(origin), str(seed))
    _git(seed, "config", "user.name", "seed")
    _git(seed, "config", "user.email", "seed@test")
    (seed / "REF-Alpha.md").write_text("alpha v1\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "push", "origin", "main")
    return origin


@pytest.fixture
def sync(tmp_path: Path, upstream: Path) -> CliGitSync:
    """A CliGitSync over a fresh clone of the upstream."""
    clone = tmp_path / "clone"
    git = CliGitSync(clone, remote_url=str(upstream))
    git.ensure_ready()
    return git


def _move_upstream(tmp_path: Path, upstream: Path, content: str) -> None:
    """Advance upstream main from a second clone (another writer)."""
    other = tmp_path / "other"
    if not other.exists():
        _git(tmp_path, "clone", str(upstream), str(other))
        _git(other, "config", "user.name", "other")
        _git(other, "config", "user.email", "other@test")
    else:
        _git(other, "pull", "--rebase")
    (other / "REF-Alpha.md").write_text(content, encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-m", "other writer")
    _git(other, "push")


class TestCliGitSync:
    def test_ensure_ready_clones_on_first_start(
        self, sync: CliGitSync, tmp_path: Path, upstream: Path
    ) -> None:
        assert (tmp_path / "clone" / ".git").is_dir()
        assert (tmp_path / "clone" / "REF-Alpha.md").read_text(encoding="utf-8") == "alpha v1\n"
        assert _git(tmp_path / "clone", "remote", "get-url", "origin").strip() == str(upstream)

    def test_restart_applies_rotated_origin_and_preserves_local_work(
        self, sync: CliGitSync, tmp_path: Path
    ) -> None:
        clone = tmp_path / "clone"
        old_url = "https://x-access-token:old-token@example.com/acme/corpus.git"
        new_url = "https://x-access-token:new-token@example.com/acme/corpus.git"
        _git(clone, "remote", "set-url", "origin", old_url)
        (clone / "REF-Beta.md").write_text("local commit\n", encoding="utf-8")
        sync.commit_all(message="local edit", author=_SERVICE)
        head = _git(clone, "rev-parse", "HEAD")
        (clone / "REF-Alpha.md").write_text("dirty edit\n", encoding="utf-8")
        (clone / "untracked.md").write_text("untracked\n", encoding="utf-8")
        state = _git(clone, "status", "--porcelain")

        restarted = CliGitSync(clone, remote_url=new_url)
        restarted.ensure_ready()
        restarted.ensure_ready()

        assert _git(clone, "remote", "get-url", "origin").strip() == new_url
        assert _git(clone, "rev-parse", "HEAD") == head
        assert _git(clone, "status", "--porcelain") == state
        assert (clone / "REF-Beta.md").read_text(encoding="utf-8") == "local commit\n"
        assert (clone / "REF-Alpha.md").read_text(encoding="utf-8") == "dirty edit\n"
        assert (clone / "untracked.md").read_text(encoding="utf-8") == "untracked\n"

    @pytest.mark.parametrize("remote_url", [None, ""])
    def test_restart_without_configured_url_preserves_origin(
        self, sync: CliGitSync, tmp_path: Path, remote_url: str | None
    ) -> None:
        clone = tmp_path / "clone"
        origin = _git(clone, "remote", "get-url", "origin")
        CliGitSync(clone, remote_url=remote_url).ensure_ready()
        assert _git(clone, "remote", "get-url", "origin") == origin

    def test_commit_all_records_pending_changes(self, sync: CliGitSync, tmp_path: Path) -> None:
        clone = tmp_path / "clone"
        (clone / "REF-Alpha.md").write_text("alpha v2\n", encoding="utf-8")
        sync.commit_all(message="docs(REF-Alpha): edit section 1", author=_SERVICE)
        assert sync.status().unpushed_commits == 1
        assert "REF-Alpha.md" in sync.status().diff_stat

    def test_commit_all_on_clean_tree_is_a_no_op(self, sync: CliGitSync) -> None:
        sync.commit_all(message="nothing changed", author=_SERVICE)
        assert sync.status().unpushed_commits == 0

    @intent("INT-SYNC-004")
    def test_a_commit_names_its_author_and_keeps_the_service_as_committer(
        self, sync: CliGitSync, tmp_path: Path
    ) -> None:
        clone = tmp_path / "clone"
        (clone / "REF-Alpha.md").write_text("alpha by ana\n", encoding="utf-8")
        sync.commit_all(message="docs(REF-Alpha): edit", author=Actor("Ana", "ana@example.com"))
        (clone / "REF-Alpha.md").write_text("alpha by the service\n", encoding="utf-8")
        sync.commit_all(message="docs(REF-Alpha): edit again", author=_SERVICE)
        log = _git(clone, "log", "-2", "--format=%ae|%ce").splitlines()
        assert log == [
            "playbook-studio@localhost|playbook-studio@localhost",
            "ana@example.com|playbook-studio@localhost",
        ]
        assert _git(clone, "log", "-1", "--skip=1", "--format=%an").strip() == "Ana"

    def test_push_publishes_and_clears_status(self, sync: CliGitSync, tmp_path: Path) -> None:
        clone = tmp_path / "clone"
        (clone / "REF-Alpha.md").write_text("alpha v2\n", encoding="utf-8")
        sync.commit_all(message="edit", author=_SERVICE)
        sync.push()
        assert sync.status().unpushed_commits == 0

    @intent("INT-SYNC-002")
    def test_push_after_upstream_moved_is_rejected_then_rebases(
        self, sync: CliGitSync, tmp_path: Path, upstream: Path
    ) -> None:
        clone = tmp_path / "clone"
        (clone / "REF-Beta.md").write_text("beta v1\n", encoding="utf-8")
        sync.commit_all(message="local edit", author=_SERVICE)
        _move_upstream(tmp_path, upstream, "alpha moved\n")
        with pytest.raises(SyncRejectedError):
            sync.push()
        sync.pull()
        sync.push()
        assert sync.status().unpushed_commits == 0

    def test_pull_with_a_dirty_clone_autostashes_instead_of_aborting(
        self, sync: CliGitSync, tmp_path: Path
    ) -> None:
        # An out-of-band, uncommitted write into the clone used to make
        # `git pull --rebase` abort ("cannot pull with rebase: You have unstaged
        # changes"), breaking the poll and every manual refresh. --autostash keeps
        # the pull working and preserves the stray change rather than aborting.
        clone = tmp_path / "clone"
        (clone / "REF-Alpha.md").write_text("alpha dirty out-of-band\n", encoding="utf-8")
        sync.pull()
        assert (clone / "REF-Alpha.md").read_text(encoding="utf-8") == "alpha dirty out-of-band\n"
        assert sync.status().unpushed_commits == 0

    @intent("INT-SYNC-002")
    def test_conflicting_histories_surface_files_and_abort(
        self, sync: CliGitSync, tmp_path: Path, upstream: Path
    ) -> None:
        clone = tmp_path / "clone"
        (clone / "REF-Alpha.md").write_text("alpha local\n", encoding="utf-8")
        sync.commit_all(message="local edit", author=_SERVICE)
        _move_upstream(tmp_path, upstream, "alpha upstream\n")
        with pytest.raises(SyncConflictError) as excinfo:
            sync.pull()
        assert excinfo.value.files == ["REF-Alpha.md"]
        # The rebase is aborted: the tree is usable and the local commit intact.
        assert sync.status().unpushed_commits == 1
        assert (clone / "REF-Alpha.md").read_text(encoding="utf-8") == "alpha local\n"


class TestUpstreamIdentity:
    """The clone names its own upstream, so no consumer carries a repo literal."""

    @intent("INT-SYNC-003")
    def test_status_reports_the_owner_name_of_the_remote_it_pushes_to(
        self, sync: CliGitSync, tmp_path: Path
    ) -> None:
        # A local bare origin has no owner/name, so re-point the clone at a
        # host-shaped URL - what a deployed studio actually clones from.
        _git(tmp_path / "clone", "remote", "set-url", "origin",
             "https://github.com/example-org/playbook.git")
        assert sync.status().repo == "example-org/playbook"

    @intent("INT-SYNC-003")
    def test_a_credentialed_remote_never_publishes_its_token(
        self, sync: CliGitSync, tmp_path: Path
    ) -> None:
        # The deployed remote carries a PAT in its userinfo. The slug is the
        # whole published value, so the credential cannot ride along.
        _git(tmp_path / "clone", "remote", "set-url", "origin",
             "https://x-access-token:ghp_supersecrettoken@github.com/acme/corpus.git")
        status = sync.status()
        assert status.repo == "acme/corpus"
        assert "ghp_supersecrettoken" not in status.repo

    @intent("INT-SYNC-003")
    def test_a_clone_with_no_host_upstream_reports_unknown_not_a_guess(
        self, sync: CliGitSync
    ) -> None:
        # The fixture's origin is a filesystem path: there is no owner/name to
        # report, and "" (unknown) is the honest answer a caller must handle.
        assert sync.status().repo == ""

    @pytest.mark.parametrize(
        ("remote", "expected"),
        [
            ("https://github.com/owner/name.git", "owner/name"),
            ("https://github.com/owner/name", "owner/name"),
            ("git@github.com:owner/name.git", "owner/name"),
            ("ssh://git@ghe.internal:2222/owner/name.git", "owner/name"),
            ("https://user:pass@gitlab.example.com/group/sub/name.git", "sub/name"),
            ("/srv/git/origin.git", ""),
            (r"C:\Users\dev\origin.git", ""),
            ("file:///srv/git/origin.git", ""),
            ("", ""),
        ],
    )
    @intent("INT-SYNC-003")
    def test_slug_derivation_across_remote_shapes(self, remote: str, expected: str) -> None:
        assert slug_from_remote(remote) == expected
