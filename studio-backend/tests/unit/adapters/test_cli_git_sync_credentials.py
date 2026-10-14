"""Credential-bearing Git diagnostics stay safe at the adapter boundary."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from studio.adapters.outbound.git_cli.cli_git_sync import CliGitSync
from studio.domain.exceptions.sync_failed_error import SyncFailedError


@pytest.mark.parametrize("failure", ["stderr", "timeout"])
@pytest.mark.parametrize("operation", ["clone", "restart", "pull", "push"])
def test_git_failures_hide_url_credentials_and_keep_diagnostics(
    failure: str, operation: str
) -> None:
    url = "https://x-access-token:synthetic-secret@example.com/acme/corpus.git"
    sync = CliGitSync(Path("unused-checkout"), remote_url=url)
    result = subprocess.CompletedProcess(
        ["git"], 1, "", f"fatal: Authentication failed for '{url}'"
    )
    timeout = subprocess.TimeoutExpired(["git", "clone", url], 120)
    with (
        patch.object(Path, "is_dir", return_value=operation == "restart"),
        patch(
            "studio.adapters.outbound.git_cli.cli_git_sync.subprocess.run",
            return_value=result,
            side_effect=timeout if failure == "timeout" else None,
        ),
        patch("studio.adapters.outbound.git_cli.cli_git_sync.logger") as logger,
        pytest.raises(SyncFailedError) as excinfo,
    ):
        getattr(sync, "ensure_ready" if operation in {"clone", "restart"} else operation)()

    assert "synthetic-secret" not in str(logger.mock_calls)
    assert "x-access-token" not in str(logger.mock_calls)

    message = str(excinfo.value)
    assert "synthetic-secret" not in message
    assert "x-access-token" not in message
    assert "example.com/acme/corpus.git" in message
    assert ("Authentication failed" if failure == "stderr" else "timed out") in message
