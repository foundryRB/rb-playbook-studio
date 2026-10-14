"""PlaybookValidator that shells out to the playbook's own gates."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["SubprocessPlaybookValidator", "corpus_code_env"]

logger = get_logger(__name__)

_TIMEOUT_SECONDS = 180
# What a copy for the gates leaves out: the clone's git directory (its config
# carries the remote's credential) and caches no gate reads.
_NOT_COPIED = shutil.ignore_patterns(
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "node_modules"
)
_STUDIO_PREFIX = "STUDIO_"


def corpus_code_env() -> dict[str, str]:
    """The environment code from the corpus runs under: the process's own, minus
    every STUDIO_ setting, which is where the studio's credentials live."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(_STUDIO_PREFIX)}


def _reap(uid: int) -> None:
    """End every process the gates user still runs once the gates are done, so
    nothing they started outlives the judgement it was part of."""
    import signal

    for _ in range(5):
        found = False
        for status in Path("/proc").glob("[0-9]*/status"):
            try:
                uids = next(
                    line.split()[1:]
                    for line in status.read_text().splitlines()
                    if line.startswith("Uid:")
                )
                if int(uids[0]) == uid:
                    found = True
                    os.kill(int(status.parent.name), signal.SIGKILL)
            except (OSError, StopIteration, ValueError, IndexError):
                continue
        if not found:
            return


class SubprocessPlaybookValidator:
    """Runs the intent-test suite and link checker over a copy of the checkout.

    The suite runs code the corpus carries (skill scripts among it), and the
    people who own that code are not all admins. So the gates judge a copy of the
    tree, without its git directory, in subprocesses whose environment holds none
    of the studio's settings. Given `run_as` (the deployed image names an
    unprivileged `gates` user), they also run as that user, who owns the copy and
    nothing else: the clone is closed to every user but the studio's own
    (CliGitSync), and the studio's process environment is unreadable to others,
    so the code can neither change the clone a write commits nor read its
    credentials, by any path.
    """

    def __init__(
        self,
        playbook_root: Path,
        python_executable: str | None = None,
        run_as: str | None = None,
    ) -> None:
        self._root = playbook_root
        self._python = python_executable or sys.executable
        self._run_as = run_as

    def validate(self) -> ValidationReport:
        with tempfile.TemporaryDirectory(
            prefix="playbook-gates-", ignore_cleanup_errors=True
        ) as scratch:
            home = Path(scratch)
            copy = home / "playbook"
            shutil.copytree(self._root, copy, ignore=_NOT_COPIED, symlinks=True)
            try:
                identity = self._hand_over(home)
            except (KeyError, OSError) as exc:
                # Refuse rather than run the corpus's code with the studio's rights.
                logger.error("Cannot run the gates as %s: %s", self._run_as, exc)
                failure = f"the gates could not run as {self._run_as!r}: {exc}"
                return ValidationReport(
                    tests_passed=False, links_ok=False, tests_output=failure, links_output=""
                )
            try:
                argv_tests = [self._python, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
                tests_rc, tests_out = self._run(argv_tests, copy, home, identity)
                argv_links = [self._python, "scripts/check_links.py"]
                links_rc, links_out = self._run(argv_links, copy, home, identity)
            finally:
                if identity is not None:
                    _reap(identity[0])
        logger.info("Validation gates: pytest rc=%d, check_links rc=%d", tests_rc, links_rc)
        return ValidationReport(
            tests_passed=tests_rc == 0,
            links_ok=links_rc == 0,
            tests_output=tests_out,
            links_output=links_out,
        )

    def _hand_over(self, home: Path) -> tuple[int, int] | None:
        """Give the scratch and its copy to the gates user; (uid, gid), or None
        when the gates run as the studio itself (a local run)."""
        if not self._run_as:
            return None
        import pwd  # POSIX only, like switching users

        entry = pwd.getpwnam(self._run_as)
        for directory, dirs, files in os.walk(home):
            os.chown(directory, entry.pw_uid, entry.pw_gid)
            for name in dirs + files:
                os.chown(
                    os.path.join(directory, name), entry.pw_uid, entry.pw_gid, follow_symlinks=False
                )
        return entry.pw_uid, entry.pw_gid

    def _run(
        self, argv: list[str], cwd: Path, home: Path, identity: tuple[int, int] | None
    ) -> tuple[int, str]:
        env = corpus_code_env()
        switch: dict[str, object] = {}
        if identity is not None:
            env.update(HOME=str(home), USER=str(self._run_as), LOGNAME=str(self._run_as))
            switch = {"user": identity[0], "group": identity[1], "extra_groups": []}
        try:
            proc = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_TIMEOUT_SECONDS,
                **switch,  # type: ignore[arg-type]
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("Validation command failed to run: %s", exc)
            return 1, str(exc)
        return proc.returncode, (proc.stdout + proc.stderr)[-8000:]
