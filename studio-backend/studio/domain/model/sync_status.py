"""Value object: the state of the working clone relative to its upstream."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SyncStatus"]


@dataclass(frozen=True)
class SyncStatus:
    """Unpushed local commits, a diffstat of what publishing would send, and
    the identity of the upstream they would go to.

    ``repo`` is the ``owner/name`` slug the working clone pushes to - the
    content repo's identity, derived from the clone the studio already owns
    rather than configured a second time. It answers "which repo IS the
    playbook?" for any caller that must act on it (filing a ticket against
    it, say) without that caller carrying a literal that a rename or an org
    move would silently strand. Empty means the clone has no such upstream
    (the local composition, or a remote that is a bare filesystem path).
    """

    unpushed_commits: int
    diff_stat: str
    repo: str = ""
