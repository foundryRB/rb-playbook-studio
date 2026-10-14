"""GitSync over the git CLI, managing a clone the studio owns."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from studio.domain.exceptions.sync_conflict_error import SyncConflictError
from studio.domain.exceptions.sync_failed_error import SyncFailedError
from studio.domain.exceptions.sync_rejected_error import SyncRejectedError
from studio.domain.model.actor import Actor
from studio.domain.model.sync_status import SyncStatus
from studio.logging import get_logger

__all__ = ["CliGitSync", "slug_from_remote"]

logger = get_logger(__name__)

_TIMEOUT_SECONDS = 120
_REJECTION_MARKERS = ("non-fast-forward", "fetch first", "[rejected]", "cannot lock ref")
_URL_USERINFO = re.compile(r"(\w+://)[^/\s]+@")


def slug_from_remote(url: str) -> str:
    """Reduce a git remote URL to its ``owner/name`` slug, or "" if it has none.

    Only the slug is ever derived, never a cleaned-up URL: a deployed studio
    clones from a URL carrying a PAT in its userinfo, and this value is
    published to every MCP and HTTP caller. Reducing to two path segments
    drops the credential by construction rather than by a filter someone
    must remember to keep.

    Handles the three shapes a remote takes - ``https://host/owner/name.git``
    (with or without userinfo), scp-style ``git@host:owner/name.git``, and a
    plain filesystem path (which has no slug, so "").
    """
    text = url.strip()
    if not text:
        return ""
    if "://" not in text:
        # scp-style is host:path with no scheme. A Windows path (C:\...) and a
        # bare POSIX path both fail this shape and correctly yield no slug.
        host, sep, path = text.partition(":")
        if not sep or len(host) < 2 or "/" in host or "\\" in host:
            return ""
        text = f"ssh://{host}/{path}"
    parts = urlsplit(text)
    if not parts.hostname:
        return ""
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:
        return ""
    owner, name = segments[-2], segments[-1]
    return f"{owner}/{name.removesuffix('.git')}"


class CliGitSync:
    """Implements GitSync with subprocess git in the checkout directory.

    ensure_ready() provisions the clone and applies the configured origin and
    author identity; afterwards every operation assumes a valid git work tree.
    """

    def __init__(
        self,
        root: Path,
        remote_url: str | None = None,
        author_name: str = "playbook-studio",
        author_email: str = "playbook-studio@localhost",
    ) -> None:
        self._root = root
        self._remote_url = remote_url
        self._author_name = author_name
        self._author_email = author_email

    def ensure_ready(self) -> None:
        """Clone on first start and apply origin and author identity in local config."""
        if not (self._root / ".git").is_dir():
            if not self._remote_url:
                raise SyncFailedError(f"no git checkout at {self._root} and no remote URL to clone")
            logger.info("Cloning content repo into %s", self._root)
            self._run_or_raise(["clone", self._remote_url, str(self._root)], cwd=self._root.parent)
        elif self._remote_url:
            self._run_or_raise(["remote", "set-url", "origin", self._remote_url])
            logger.info("Applied configured content origin")
        self._run_or_raise(["config", "user.name", self._author_name])
        self._run_or_raise(["config", "user.email", self._author_email])
        if os.name == "posix":
            # The clone is the studio's alone: its git config carries the remote's
            # credential, and its files are what a write commits. Code the gates
            # run as another user can neither enter nor change it.
            os.chmod(self._root, 0o700)

    def commit_all(self, *, message: str, author: Actor) -> None:
        """Stage everything and commit as `author`; a clean tree is a silent no-op.

        The author is the person who made the change; the clone's configured
        identity (the service) stays the committer and the pusher.
        """
        self._run_or_raise(["add", "-A"])
        rc, out = self._run(["diff", "--cached", "--quiet"])
        if rc == 0:
            logger.info("Nothing to commit for: %s", message)
            return
        self._run_or_raise(["commit", f"--author={author.name} <{author.email}>", "-m", message])
        logger.info("Committed gated edit by %s: %s", author.email, message)

    def pull(self) -> None:
        """Rebase onto upstream head; surface conflicts raw and abort the rebase.

        `--autostash` keeps sync alive if the clone is ever left dirty. A studio
        edit never leaves it dirty (it commits or rolls back), but an out-of-band
        write into the working tree would otherwise make every `pull --rebase`
        abort with "cannot pull with rebase: You have unstaged changes" -- breaking
        both the poll and every manual refresh until a human intervenes. Autostash
        stashes the stray change, rebases, and reapplies it instead of aborting.
        """
        rc, out = self._run(["pull", "--rebase", "--autostash"])
        if rc == 0:
            logger.info("Pulled upstream head")
            return
        conflicted = self._conflicted_files()
        if conflicted:
            self._run(["rebase", "--abort"])
            logger.warning("Pull hit a conflict in: %s", ", ".join(conflicted))
            raise SyncConflictError(conflicted)
        raise SyncFailedError(out.strip()[-2000:])

    def push(self) -> None:
        """Publish local commits; classify a non-fast-forward as a rejection."""
        rc, out = self._run(["push"])
        if rc == 0:
            logger.info("Pushed local commits upstream")
            return
        lowered = out.lower()
        if any(marker in lowered for marker in _REJECTION_MARKERS):
            raise SyncRejectedError(out.strip()[-2000:])
        raise SyncFailedError(out.strip()[-2000:])

    def status(self) -> SyncStatus:
        """Count commits ahead of upstream, diffstat a push, and name the upstream."""
        repo = self._repo_slug()
        rc, count_out = self._run(["rev-list", "--count", "@{upstream}..HEAD"])
        if rc != 0:
            return SyncStatus(unpushed_commits=0, diff_stat="", repo=repo)
        unpushed = int(count_out.strip() or "0")
        diff_stat = ""
        if unpushed:
            rc, diff_out = self._run(["diff", "--stat", "@{upstream}..HEAD"])
            diff_stat = diff_out.strip() if rc == 0 else ""
        return SyncStatus(unpushed_commits=unpushed, diff_stat=diff_stat, repo=repo)

    def _repo_slug(self) -> str:
        """The ``owner/name`` this clone pushes to, read from the clone itself.

        Asking git, not the configured ``remote_url``, keeps the answer true
        after any out-of-band ``git remote set-url``: what the clone actually
        pushes to is what it reports.
        """
        rc, out = self._run(["remote", "get-url", "origin"])
        return slug_from_remote(out) if rc == 0 else ""

    def _conflicted_files(self) -> list[str]:
        rc, out = self._run(["diff", "--name-only", "--diff-filter=U"])
        if rc != 0:
            return []
        return [line.strip() for line in out.splitlines() if line.strip()]

    def _run(self, argv: list[str], cwd: Path | None = None) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                ["git", *argv],
                cwd=cwd or self._root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, _URL_USERINFO.sub(r"\1[redacted]@", str(exc))
        output = proc.stdout + proc.stderr
        if proc.returncode != 0:
            output = _URL_USERINFO.sub(r"\1[redacted]@", output)
        return proc.returncode, output

    def _run_or_raise(self, argv: list[str], cwd: Path | None = None) -> str:
        rc, out = self._run(argv, cwd=cwd)
        if rc != 0:
            raise SyncFailedError(f"git {argv[0]}: {out.strip()[-2000:]}")
        return out
