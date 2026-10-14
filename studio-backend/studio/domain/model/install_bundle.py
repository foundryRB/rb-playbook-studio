"""The whole installable toolchain for one harness, as one artifact."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from studio.domain.model.bundle_file import BundleFile

__all__ = ["AGENTS_PREFIX", "SKILLS_PREFIX", "InstallBundle"]

#: Where a bundle holds each skill's folder and each rendered agent file.
SKILLS_PREFIX = "skills/"
AGENTS_PREFIX = "agents/"


@dataclass(frozen=True)
class InstallBundle:
    """Every skill and every agent, rendered for one harness, with the playbook
    installer that applies them.

    The bundle is the per-skill path in one artifact: the files a client would
    have fetched one tool call at a time, gathered so a script can apply them and
    the model never carries them. Where each file lands is the installer's to decide,
    from its place in the bundle and the installer's own options.
    """

    runtime: str
    files: tuple[BundleFile, ...]
    installer: bytes

    @property
    def digest(self) -> str:
        """A digest over every file in the bundle: its path, sha256, and executable bit.

        Content-addressed, so it moves exactly when an installed file would.
        """
        ordered = sorted(self.files, key=lambda f: f.path)
        listing = "".join(f"{f.path}\0{f.sha256}\0{int(f.executable)}\n" for f in ordered)
        return hashlib.sha256(listing.encode("utf-8")).hexdigest()
