"""MCP integration tests: a real server exercised through the protocol client."""

from __future__ import annotations

import base64
import json
import os
import socket
import threading
import time
from pathlib import Path
from types import TracebackType

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent

from studio.adapters.inbound.http.app import create_app
from studio.container import Container
from tests.conftest import FakeGitSync, StubValidator


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _Server:
    """Uvicorn on an ephemeral port, running the app for the test's duration."""

    def __init__(self, container: Container) -> None:
        port = _free_port()
        config = uvicorn.Config(
            create_app(container), host="127.0.0.1", port=port, log_level="warning"
        )
        self.base_url = f"http://127.0.0.1:{port}"
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> _Server:
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


def _managed_container(
    playbook_root: Path, git: FakeGitSync, ok: bool = True
) -> Container:
    return Container(
        playbook_root=playbook_root,
        validator=StubValidator(ok=ok),
        runtime_skills_dir=playbook_root / "_runtime",
        git_sync=git,
    )


async def _tool_names(base_url: str) -> set[str]:
    async with (
        streamable_http_client(f"{base_url}/mcp") as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        return {tool.name for tool in tools.tools}


class TestMcpSurface:
    @pytest.mark.anyio
    async def test_tools_mirror_inbound_ports(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            names = await _tool_names(srv.base_url)
        assert {
            "get_graph",
            "get_playbook",
            "get_ref",
            "get_skill",
            "get_skill_files",
            "list_agents",
            "get_agent",
            "get_agent_files",
            "create_agent",
            "update_agent_document",
            "list_claims",
            "run_validation",
            "update_ref_section",
            "update_playbook_document",
            "update_galaxy_document",
            "create_ref",
            "create_skill",
            "get_install_command",
        } <= names

    @intent("INT-MCP-002")
    @pytest.mark.anyio
    async def test_sync_tools_follow_the_capability_wiring(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            managed = await _tool_names(srv.base_url)
        local = Container(
            playbook_root=playbook_root,
            validator=StubValidator(ok=True),
            runtime_skills_dir=playbook_root / "_runtime",
        )
        with _Server(local) as srv:
            operator_owned = await _tool_names(srv.base_url)
        assert {"push_changes", "refresh_content", "get_sync_status"} <= managed
        assert not {"push_changes", "refresh_content", "get_sync_status"} & operator_owned

    @pytest.mark.anyio
    async def test_read_tool_returns_parsed_content(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool("get_ref", {"name": "REF-Alpha"})
        assert not result.isError
        assert "Alpha conventions." in str(result.content)

    @pytest.mark.anyio
    async def test_agent_roster_is_served(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                roster = await session.call_tool("list_agents", {})
                detail = await session.call_tool("get_agent", {"name": "alpha-agent"})
        assert not roster.isError
        assert "alpha-agent" in str(roster.content)
        assert not detail.isError
        assert "Runs the alpha thing end to end." in str(detail.content)


class TestMcpQuarantine:
    @intent("INT-QUAR-001")
    @pytest.mark.anyio
    async def test_nebulae_never_cross_the_door(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        """The fixture corpus carries nebulae/deep-sea-mining with three notes;
        the MCP surface registers no nebula tool and get_graph carries none of it."""
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                graph = await session.call_tool("get_graph", {})
        assert not any("nebula" in name or "stardust" in name for name in names)
        assert not graph.isError
        graph_text = str(graph.content)
        for stardust in (
            "deep-sea-mining",
            "nodule-harvesters",
            "isa-regulation",
            "seat-operator",
        ):
            assert stardust not in graph_text


class TestMcpOneWayIn:
    @intent("INT-INSTALL-002")
    @pytest.mark.anyio
    async def test_the_install_is_reached_through_the_tool_alone(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        """No prompt and no skill name: a fresh machine reaches the install through
        get_install_command, which the server's instructions name. The names checked
        are the suite's skills, the prompt the door served before the tool, the
        playbook's own install skill, and, with STUDIO_TEST_PLAYBOOK_ROOT set to a
        playbook checkout, every skill it holds."""
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                init = await session.initialize()
                prompts = await session.list_prompts()
        assert prompts.prompts == []
        instructions = init.instructions or ""
        assert "get_install_command" in instructions
        names = {d.name for d in (playbook_root / "skills").iterdir()}
        names |= {"install-skill", "install-playbook"}
        checkout = os.environ.get("STUDIO_TEST_PLAYBOOK_ROOT")
        if checkout:
            names |= {p.parent.name for p in Path(checkout).glob("galaxies/*/skills/*/SKILL.md")}
        assert not sorted(name for name in names if name in instructions), "no skill is named"


class TestMcpDeploymentSurface:
    @pytest.mark.anyio
    async def test_bare_mcp_path_works_with_the_spa_mounted(
        self,
        playbook_root: Path,
        fake_git: FakeGitSync,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Clients connect to /mcp (no slash); the SPA mount at / must not swallow it."""
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
        monkeypatch.setenv("STUDIO_FRONTEND_DIST", str(dist))
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            names = await _tool_names(srv.base_url)
        assert "get_ref" in names

    @pytest.mark.anyio
    async def test_allowed_hosts_gate_the_transport(
        self,
        playbook_root: Path,
        fake_git: FakeGitSync,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A deployment allows its public hostname; other Host values answer 421."""
        import httpx

        initialize = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0"},
            },
        }
        headers = {"Accept": "application/json, text/event-stream"}
        monkeypatch.setenv("STUDIO_MCP_ALLOWED_HOSTS", "studio.example.test")
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with httpx.AsyncClient() as client:
                wrong_host = await client.post(
                    f"{srv.base_url}/mcp/", json=initialize, headers=headers
                )
                right_host = await client.post(
                    f"{srv.base_url}/mcp/",
                    json=initialize,
                    headers={**headers, "Host": "studio.example.test"},
                )
        assert wrong_host.status_code == 421
        assert right_host.status_code == 200


class TestMcpGatedWrites:
    @intent("INT-MCP-001")
    @pytest.mark.anyio
    async def test_write_tool_commits_when_gates_pass(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    "update_ref_section",
                    {
                        "ref_name": "REF-Alpha",
                        "number": 1,
                        "body": "Always be Alpha, via MCP. See `REF-Beta.md`.",
                    },
                )
        assert not result.isError
        assert "via MCP" in (playbook_root / "REF-Alpha.md").read_text(encoding="utf-8")
        assert fake_git.commits == ["docs(REF-Alpha): edit section 1"]

    @intent("INT-MCP-001")
    @pytest.mark.anyio
    async def test_rejected_write_rolls_back_and_reports(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        original = (playbook_root / "REF-Alpha.md").read_text(encoding="utf-8")
        with _Server(_managed_container(playbook_root, fake_git, ok=False)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    "update_ref_section",
                    {"ref_name": "REF-Alpha", "number": 1, "body": "must not survive"},
                )
        assert result.isError
        assert "rejected by the validation gates" in str(result.content)
        assert (playbook_root / "REF-Alpha.md").read_text(encoding="utf-8") == original
        assert fake_git.commits == []

    @intent("INT-GATE-001")
    @pytest.mark.anyio
    async def test_galaxy_document_is_writable_through_the_door(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        """A GALAXY.md edit lands over MCP instead of forcing a local clone (#16)."""
        galaxy_path = playbook_root / "galaxies" / "craft" / "GALAXY.md"
        edited = galaxy_path.read_text(encoding="utf-8").replace(
            "1. **Do not duplicate.**",
            "1. **Do not duplicate.**\n2. **No em-dashes.**",
        )
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    "update_galaxy_document",
                    {"name": "craft", "raw": edited},
                )
        assert not result.isError
        assert "No em-dashes" in galaxy_path.read_text(encoding="utf-8")
        assert fake_git.commits == ["docs(galaxy): replace craft GALAXY.md"]

    @intent("INT-GATE-001")
    @pytest.mark.anyio
    async def test_rejected_galaxy_write_rolls_back_and_reports(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        galaxy_path = playbook_root / "galaxies" / "craft" / "GALAXY.md"
        original = galaxy_path.read_text(encoding="utf-8")
        with _Server(_managed_container(playbook_root, fake_git, ok=False)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    "update_galaxy_document",
                    {"name": "craft", "raw": "must not survive"},
                )
        assert result.isError
        assert "rejected by the validation gates" in str(result.content)
        assert galaxy_path.read_text(encoding="utf-8") == original
        assert fake_git.commits == []

    @intent("INT-MCP-001")
    @pytest.mark.anyio
    async def test_rejected_agent_write_rolls_back_and_reports(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        agent_path = playbook_root / "galaxies" / "craft" / "agents" / "alpha-agent.md"
        original = agent_path.read_text(encoding="utf-8")
        with _Server(_managed_container(playbook_root, fake_git, ok=False)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    "update_agent_document",
                    {"name": "alpha-agent", "raw": "must not survive"},
                )
        assert result.isError
        assert "rejected by the validation gates" in str(result.content)
        assert agent_path.read_text(encoding="utf-8") == original
        assert fake_git.commits == []

    @pytest.mark.anyio
    async def test_skill_files_ship_for_client_side_install(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool("get_skill_files", {"name": "do-alpha"})
        assert not result.isError
        text = str(result.content)
        assert "SKILL.md" in text
        assert "Do the alpha thing." in text

    @intent("INT-MCP-003")
    @pytest.mark.anyio
    async def test_agent_files_ship_rendered_for_every_harness(
        self, playbook_root: Path, fake_git: FakeGitSync
    ) -> None:
        # The roster's half of the client-executes idiom. The studio must serve the
        # installer's rendering, not one of its own: the marker only exists there.
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                every = await session.call_tool("get_agent_files", {"name": "alpha-agent"})
                one = await session.call_tool(
                    "get_agent_files", {"name": "alpha-agent", "runtime": "opencode"}
                )
                unknown = await session.call_tool(
                    "get_agent_files", {"name": "alpha-agent", "runtime": "emacs"}
                )
        assert not every.isError
        text = str(every.content)
        assert "rendered-by-installer: claude-shape" in text, "the installer rendered it"
        assert "rendered-by-installer: opencode-shape" in text, "every harness is served"
        assert "alpha-agent.md" in text and "~/.config/opencode/agents/" in text

        assert not one.isError
        named = str(one.content)
        assert "opencode-shape" in named and "claude-shape" not in named

        assert unknown.isError, "a harness the playbook cannot render for is named, not empty"


class TestMcpInstallCommand:
    @intent("INT-AUTH-006")
    @pytest.mark.anyio
    async def test_the_command_carries_a_download_token_never_the_credential(
        self, playbook_root: Path, fake_git: FakeGitSync, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The connector holds the Basic credential; the line it gets back to run in a
        shell carries only a token the door minted, which the gate admits on the
        install routes and nowhere else."""
        monkeypatch.setenv("STUDIO_AUTH_DISABLED", "false")
        monkeypatch.setenv("STUDIO_AUTH_USER", "ops")
        monkeypatch.setenv("STUDIO_AUTH_PASSWORD", "s3cret")
        credential = base64.b64encode(b"ops:s3cret").decode()
        headers = {"Authorization": f"Basic {credential}"}
        with _Server(_managed_container(playbook_root, fake_git)) as srv:
            async with (
                httpx.AsyncClient(headers=headers) as http,
                streamable_http_client(f"{srv.base_url}/mcp", http_client=http) as (r, w, _),
                ClientSession(r, w) as session,
            ):
                await session.initialize()
                result = await session.call_tool("get_install_command", {"runtime": "opencode"})
                unknown = await session.call_tool("get_install_command", {"runtime": "emacs"})
            command = result.structuredContent or json.loads(result.content[0].text)
            async with httpx.AsyncClient() as anonymous:
                script = command["posix"].split("'")[1]
                served = await anonymous.get(script)
                bundle = await anonymous.get(served.text.split("bundle_url='")[1].split("'")[0])
                elsewhere = await anonymous.get(f"{srv.base_url}/api/graph")

        assert not result.isError
        text = json.dumps(command)
        assert credential not in text and "s3cret" not in text
        assert command["posix"].startswith(f"curl -fsSL '{srv.base_url}/mcp/install/")
        assert command["posix"].endswith("/install.sh?runtime=opencode' | sh -s --")
        assert "/install.ps1?runtime=opencode'" in command["powershell"]
        assert command["expires_in_seconds"] == 600
        assert served.status_code == 200 and served.text.startswith("#!/bin/sh")
        assert bundle.status_code == 200
        assert bundle.headers["content-type"] == "application/gzip"
        assert elsewhere.status_code == 401
        assert unknown.isError
        assert "claude-code" in str(unknown.content) and "opencode" in str(unknown.content)
