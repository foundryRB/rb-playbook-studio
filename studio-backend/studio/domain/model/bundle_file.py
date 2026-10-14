"""One file of an install bundle."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

__all__ = ["BundleFile"]


@dataclass(frozen=True)
class BundleFile:
    """One file a client installs: its place in the bundle, its bytes, and whether it
    is executable."""

    path: str
    data: bytes
    executable: bool = False

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()
