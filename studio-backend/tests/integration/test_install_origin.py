"""The origin install lines name (#51).

A deployment answers behind a gateway that terminates TLS, and the proxies in
front of the app report the plain-http hop they received. These tests present a
request the way that gateway does and require every URL the install hands out to
name the configured https origin; a local run, with no origin configured, keeps
naming the plain-http origin its requests arrive on.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent
from starlette.requests import Request

from studio.adapters.inbound.http.installer import public_base
from tests.conftest import FakeGitSync
from tests.integration.test_mcp_api import _managed_container, _Server

_REPO = Path(__file__).resolve().parents[3]
_PUBLIC_HOST = "studio.example.test"
_ORIGIN = f"https://{_PUBLIC_HOST}"

# A request as it reaches the app behind the gateway: the public Host, and the
# plain-http hop the proxy in front of the app received.
_GATEWAY = {"Host": _PUBLIC_HOST, "X-Forwarded-Proto": "http", "X-Forwarded-Host": _PUBLIC_HOST}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _install_command(base_url: str, headers: dict[str, str]) -> dict:
    async with (
        httpx.AsyncClient(headers=headers) as http,
        streamable_http_client(f"{base_url}/mcp", http_client=http) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool("get_install_command", {"runtime": "claude-code"})
    assert not result.isError, str(result.content)
    return result.structuredContent or json.loads(result.content[0].text)


def _line_url(line: str) -> str:
    return line.split("'")[1]


def _request(host: str = "127.0.0.1:8000") -> Request:
    return Request(
        {
            "type": "http",
            "scheme": "http",
            "method": "GET",
            "path": "/",
            "server": ("127.0.0.1", 8000),
            "headers": [(b"host", host.encode())],
        }
    )


class TestInstallOrigin:
    @intent("INT-AUTH-007")
    @pytest.mark.anyio
    async def test_behind_the_gateway_every_url_names_the_https_origin(
        self, playbook_root: Path, fake_git: FakeGitSync, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The client reached the studio over https; the gateway hands the app plain http.
        The lines, and the bundle URL each script carries, name https all the same."""
        monkeypatch.setenv("STUDIO_PUBLIC_ORIGIN", _ORIGIN)
        monkeypatch.setenv("STUDIO_MCP_ALLOWED_HOSTS", _PUBLIC_HOST)
        prefix = f"{_ORIGIN}/mcp/install/"
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            command = await _install_command(srv.base_url, _GATEWAY)
            assert _line_url(command["posix"]).startswith(prefix)
            assert _line_url(command["powershell"]).startswith(prefix)
            async with httpx.AsyncClient(headers=_GATEWAY) as gateway:
                scripts = [
                    await gateway.get(_line_url(command[line]).replace(_ORIGIN, srv.base_url))
                    for line in ("posix", "powershell")
                ]

        sh, ps1 = (s.text for s in scripts)
        assert all(s.status_code == 200 for s in scripts)
        assert f"bundle_url='{prefix}" in sh
        assert f"$bundleUrl = '{prefix}" in ps1
        assert "http://" not in json.dumps(command) + sh + ps1

    @intent("INT-AUTH-007")
    @pytest.mark.anyio
    async def test_a_local_run_names_the_origin_its_requests_arrive_on(
        self, playbook_root: Path, fake_git: FakeGitSync, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No origin configured: the line, the script and the bundle all work over the
        plain http the local server answers on."""
        monkeypatch.delenv("STUDIO_PUBLIC_ORIGIN", raising=False)
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            command = await _install_command(srv.base_url, {})
            async with httpx.AsyncClient() as client:
                script = await client.get(_line_url(command["posix"]))
                bundle_url = script.text.split("bundle_url='")[1].split("'")[0]
                bundle = await client.get(bundle_url)

        assert _line_url(command["posix"]).startswith(f"{srv.base_url}/mcp/install/")
        assert bundle_url.startswith(f"{srv.base_url}/mcp/install/")
        assert bundle.status_code == 200
        assert bundle.headers["content-type"] == "application/gzip"

    @intent("INT-AUTH-007")
    def test_a_configured_origin_wins_over_the_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("STUDIO_PUBLIC_ORIGIN", f"{_ORIGIN}/")
        assert public_base(_request("internal.svc:8000")) == _ORIGIN

    @intent("INT-AUTH-007")
    @pytest.mark.parametrize(
        "origin",
        [
            _PUBLIC_HOST,
            f"ftp://{_PUBLIC_HOST}",
            f"{_ORIGIN}/mcp",
            f"{_ORIGIN}?x=1",
            f"https://user@{_PUBLIC_HOST}",
            f"{_ORIGIN}'; rm -rf ~",
            "https://[::1",
        ],
    )
    def test_a_configured_origin_that_is_not_one_is_refused(
        self, origin: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A misconfigured origin is refused with the form it should take; no line is built."""
        monkeypatch.setenv("STUDIO_PUBLIC_ORIGIN", origin)
        with pytest.raises(ValueError, match=r"^STUDIO_PUBLIC_ORIGIN must be scheme://host"):
            public_base(_request())

    @intent("INT-AUTH-007")
    def test_the_chart_configures_the_routes_hostname_over_https(self) -> None:
        """The deployment's origin is the hostname its route serves, never a second copy."""
        route = (_REPO / "k8s" / "templates" / "httproute.yaml").read_text(encoding="utf-8")
        config = (_REPO / "k8s" / "templates" / "configmap.yaml").read_text(encoding="utf-8")
        assert "- {{ .Values.host | quote }}" in route
        assert 'STUDIO_PUBLIC_ORIGIN: {{ printf "https://%s" .Values.host | quote }}' in config
