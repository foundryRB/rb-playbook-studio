"""People and a corpus with rights: the fixtures the identity and rights tests share.

The corpus is the conftest's synthetic playbook shelved into galaxies, with an
MCP card and an OWNERS file naming one person per role:

- admin@example.com owns `/` (admin)
- writer@example.com owns `galaxies/craft/` (galaxy writer)
- owner@example.com owns the do-alpha skill and the alpha-door card (atom owner)
- reader@example.com owns nothing (reader)
"""

from __future__ import annotations

import base64
import shutil
import socket
import threading
import time
from pathlib import Path
from types import TracebackType

import uvicorn
from fastapi.testclient import TestClient

from studio.adapters.inbound.http.app import create_app
from studio.container import Container
from studio.domain.model.actor import Actor
from tests.conftest import FakeGitSync, StubValidator

ADMIN = "admin@example.com"
WRITER = "writer@example.com"
OWNER = "owner@example.com"
READER = "reader@example.com"
PEOPLE = (ADMIN, WRITER, OWNER, READER)

BASIC_USER = "ops"
BASIC_PASSWORD = "s3cret"
TOKEN_KEY = "k" * 48
PROXY_SECRET = "p" * 48

OWNERS_TEXT = f"""# Who may change what in this playbook.
/                                     {ADMIN}
/galaxies/craft/                      {WRITER}
/galaxies/craft/skills/do-alpha/      {OWNER}
/galaxies/craft/mcps/alpha-door.md    {OWNER}
"""

DOOR_CARD = """---
name: {name}
galaxy: craft
refs:
  - REF-Alpha
---

# MCP: {name}

> Knock here for the alpha things.

The door to alpha.
"""

_MAKER_GALAXY = """# Galaxy: maker

The maker shelf.

## Task Routing - load only what you need

| Task | Read These REFs |
| ---- | --------------- |
"""


def shelve(root: Path, owners: str | None = OWNERS_TEXT) -> Path:
    """Shelve the conftest corpus into galaxies, add a card and a second galaxy, and
    write OWNERS (None leaves the corpus without one)."""
    craft = root / "galaxies" / "craft"
    (root / "REF-Alpha.md").replace(craft / "REF-Alpha.md")
    (craft / "skills").mkdir()
    shutil.move(str(root / "skills" / "do-alpha"), str(craft / "skills" / "do-alpha"))
    (craft / "mcps").mkdir()
    (craft / "mcps" / "alpha-door.md").write_text(
        DOOR_CARD.format(name="alpha-door"), encoding="utf-8"
    )
    maker = root / "galaxies" / "maker"
    maker.mkdir()
    (maker / "GALAXY.md").write_text(_MAKER_GALAXY, encoding="utf-8")
    if owners is not None:
        (root / "OWNERS").write_text(owners, encoding="utf-8")
    return root


def container(root: Path, git: FakeGitSync, ok: bool = True, validator=None) -> Container:
    return Container(
        playbook_root=root,
        validator=validator or StubValidator(ok=ok),
        runtime_skills_dir=root / "_runtime",
        git_sync=git,
    )


def configure_proxy_mode(monkeypatch) -> None:
    """The deployed posture: the OIDC proxy fronts humans, Basic and personal
    tokens open the machine door."""
    monkeypatch.setenv("STUDIO_AUTH_DISABLED", "false")
    monkeypatch.setenv("STUDIO_AUTH_SCOPE", "mcp")
    monkeypatch.setenv("STUDIO_AUTH_USER", BASIC_USER)
    monkeypatch.setenv("STUDIO_AUTH_PASSWORD", BASIC_PASSWORD)
    monkeypatch.setenv("STUDIO_TOKEN_KEY", TOKEN_KEY)
    monkeypatch.setenv("STUDIO_PROXY_SECRET", PROXY_SECRET)


def sidecar_client(app) -> TestClient:
    """A client whose requests arrive from loopback, as the OIDC sidecar's do."""
    return TestClient(app, client=("127.0.0.1", 50000))


def proxied(user: str = "someone", secret: str = PROXY_SECRET) -> dict[str, str]:
    """The Basic header the OIDC sidecar sets, its password the proxy secret."""
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def signed_in(email: str, name: str | None = None) -> dict[str, str]:
    """The headers the OIDC sidecar sets for a signed-in person."""
    headers = {**proxied(email), "X-Forwarded-Email": email}
    if name:
        headers["X-Forwarded-Preferred-Username"] = name
    return headers


def basic() -> dict[str, str]:
    token = base64.b64encode(f"{BASIC_USER}:{BASIC_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def bearer(app, email: str) -> dict[str, str]:
    """A personal token minted for this person by the app's own key."""
    token, _ = app.state.personal_tokens.mint(Actor(name=email.split("@")[0], email=email))
    return {"Authorization": f"Bearer {token}"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Server:
    """Uvicorn on an ephemeral port, running an app for the test's duration."""

    def __init__(self, app) -> None:
        port = _free_port()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        self.app = app
        self.base_url = f"http://127.0.0.1:{port}"
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> Server:
        self._thread.start()
        deadline = time.monotonic() + 15
        while not self._server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("test server failed to start")
            time.sleep(0.05)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)


def app_for(root: Path, git: FakeGitSync, **kwargs):
    return create_app(container(root, git, **kwargs))
