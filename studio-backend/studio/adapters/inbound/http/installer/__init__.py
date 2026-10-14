"""The toolchain install's wire formats: the bundle archive and the install scripts.

The bundle is one gzipped tar: a manifest, every file, and the playbook's own
installer at scripts/install_playbook.py, laid out so the installer runs against
the unpacked bundle exactly as it runs against a clone. The install scripts only
find Python, download the bundle, unpack it, and run that installer. Every rule
about what gets written lives in it, in the playbook; the studio holds none.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import tarfile
from pathlib import Path
from urllib.parse import urlsplit

from starlette.requests import Request

from studio.domain.model.install_bundle import InstallBundle

__all__ = [
    "INSTALLER",
    "MANIFEST",
    "bundle_archive",
    "install_script",
    "manifest",
    "public_base",
]

_HERE = Path(__file__).resolve().parent

#: Where the bundle carries the playbook installer, as a clone does.
INSTALLER = "scripts/install_playbook.py"
MANIFEST = "manifest.json"
_FORMAT = 1
_BUNDLE_URL = "__BUNDLE_URL__"

#: A Host header value fit to quote into a shell line: a name or address, a port.
_HOST = re.compile(r"(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:.]+\])(?::[0-9]{1,5})?")

#: The origin a deployment serves its clients on, as scheme://host[:port].
_PUBLIC_ORIGIN_ENV = "STUDIO_PUBLIC_ORIGIN"
_SCHEMES = ("http", "https")


def manifest(bundle: InstallBundle) -> dict[str, object]:
    """The bundle's table of contents: its harness, its digest, and per file its path,
    sha256, and executable bit."""
    return {
        "format": _FORMAT,
        "runtime": bundle.runtime,
        "digest": bundle.digest,
        "files": [
            {
                "path": f.path,
                "sha256": f.sha256,
                "executable": f.executable,
            }
            for f in bundle.files
        ],
    }


def bundle_archive(bundle: InstallBundle) -> bytes:
    """The bundle as one gzipped tar, byte-stable for the same content."""
    members = [
        (MANIFEST, (json.dumps(manifest(bundle), indent=2) + "\n").encode("utf-8"), False),
        (INSTALLER, bundle.installer, False),
        *((f.path, f.data, f.executable) for f in bundle.files),
    ]
    buffer = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as zipped,
        tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for name, data, executable in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755 if executable else 0o644
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def install_script(name: str, bundle_url: str) -> str:
    """One of the install scripts (install.sh, install.ps1), pointed at its bundle."""
    template = (_HERE / name).read_text(encoding="utf-8")
    return template.replace(_BUNDLE_URL, bundle_url)


def public_base(request: Request) -> str:
    """The scheme and host an install line names, for a client to fetch from.

    A deployment configures its public origin ($STUDIO_PUBLIC_ORIGIN, which the
    chart renders from the route's hostname), and every line names it, whatever
    the proxies in front of the app report about the hop they received. A local
    run configures none, and the line names the scheme and Host the request
    arrived with.
    """
    configured = os.environ.get(_PUBLIC_ORIGIN_ENV, "").strip()
    if configured:
        try:
            parts = urlsplit(configured)
        except ValueError:
            parts = None
        if (
            parts is None
            or parts.scheme not in _SCHEMES
            or not _HOST.fullmatch(parts.netloc)
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
        ):
            raise ValueError(
                f"{_PUBLIC_ORIGIN_ENV} must be scheme://host[:port] with an http or https "
                f"scheme: got {configured!r}"
            )
        return f"{parts.scheme}://{parts.netloc}"
    scheme, host = request.url.scheme, request.headers.get("host", "")
    if scheme not in _SCHEMES or not _HOST.fullmatch(host):
        raise ValueError(f"cannot build an install URL from scheme {scheme!r} and host {host!r}")
    return f"{scheme}://{host}"
