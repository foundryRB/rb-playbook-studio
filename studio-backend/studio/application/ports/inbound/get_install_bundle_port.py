"""Inbound port: the whole toolchain for one harness, for a one-step client install."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.install_bundle import InstallBundle

__all__ = ["GetInstallBundlePort"]


@runtime_checkable
class GetInstallBundlePort(Protocol):
    """Returns every skill and agent a client installs for one harness."""

    def execute(self, *, runtime: str) -> InstallBundle: ...
