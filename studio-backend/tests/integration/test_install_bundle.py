"""The toolchain in one download: the bundle the door serves, and the line that runs it.

Attests INT-INSTALL-001 (the bundle carries what the per-skill path serves, and one
shell call runs the playbook's own installer against it) and INT-INSTALL-002 (the
studio holds no install logic of its own).

Every test runs over the suite's fixture corpus, whose stand-in installer stands for
the playbook's. Set STUDIO_TEST_PLAYBOOK_ROOT to a playbook checkout and the
corpus-parametrized ones also run over it with its real installer, whose own rules
the playbook's suite attests; set STUDIO_TEST_FLOOR_PYTHON to a Python 3.8
interpreter to run that installer from the studio's bundle under it.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import NamedTuple

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pytest_intent import intent

from studio.adapters.inbound.http import installer
from studio.adapters.inbound.http.installer import bundle_archive
from studio.container import Container
from tests.conftest import FakeGitSync, StubValidator
from tests.integration.test_mcp_api import _Server

_CHECKOUT_ENV = "STUDIO_TEST_PLAYBOOK_ROOT"
_FLOOR_ENV = "STUDIO_TEST_FLOOR_PYTHON"
_RUNTIMES = ("claude-code", "opencode", "codex")
_INSTALLER_DIR = Path(installer.__file__).parent
_REPO = Path(__file__).resolve().parents[3]

# A file no text decoding survives, as a skill's binary asset (a template deck).
_BINARY = bytes(range(256)) * 4


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _Corpus(NamedTuple):
    root: Path
    real: bool


def _grow(root: Path) -> None:
    """The suite's corpus, plus what a real corpus carries: a galaxy skill, nested,
    binary and executable files, text with CR line endings, and a bytecode cache no
    install ever ships."""
    skill = root / "galaxies" / "craft" / "skills" / "gamma-skill"
    (skill / "assets").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: gamma-skill\ndescription: Gamma.\nrefs: []\n---\n\n# Gamma\n",
        encoding="utf-8",
    )
    (skill / "assets" / "template.bin").write_bytes(_BINARY)
    (skill / "assets" / "notes.md").write_bytes(b"one\r\ntwo\rthree\n")
    (skill / "scripts").mkdir()
    (skill / "scripts" / "run.py").write_text("print('gamma')\n", encoding="utf-8")
    (skill / "scripts" / "run.sh").write_text("#!/bin/sh\necho gamma\n", encoding="utf-8")
    (skill / "scripts" / "run.sh").chmod(0o755)
    (skill / "scripts" / "__pycache__").mkdir()
    (skill / "scripts" / "__pycache__" / "run.cpython-312.pyc").write_bytes(b"\0cache")


@pytest.fixture(params=["fixture", "checkout"])
def corpus(request: pytest.FixtureRequest, playbook_root: Path) -> _Corpus:
    if request.param == "fixture":
        _grow(playbook_root)
        return _Corpus(playbook_root, real=False)
    checkout = os.environ.get(_CHECKOUT_ENV)
    if not checkout:
        pytest.skip(f"set {_CHECKOUT_ENV} to a playbook checkout to run over the real corpus")
    return _Corpus(Path(checkout), real=True)


def _container(root: Path, tmp_path: Path) -> Container:
    return Container(
        playbook_root=root,
        validator=StubValidator(ok=True),
        runtime_skills_dir=tmp_path / "_runtime",
        git_sync=FakeGitSync(),
    )


def _unpack(container: Container, runtime: str, dest: Path) -> Path:
    """Build the bundle the door serves and unpack it, as the install script does."""
    archive = bundle_archive(container.get_install_bundle().execute(runtime=runtime))
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")
    return dest


def _executable(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


def _files(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def _decoded(entry: dict) -> bytes:
    """A served skill file as a client writes it: a base64 entry decoded, text as UTF-8."""
    if entry.get("encoding") == "base64":
        return base64.b64decode(entry["content"], validate=True)
    assert "encoding" not in entry, entry
    return entry["content"].encode("utf-8")


def _tool_json(result: object) -> dict:
    assert not result.isError, str(result.content)
    if result.structuredContent:
        return result.structuredContent
    return json.loads(result.content[0].text)


async def _per_skill_tree(base_url: str, runtime: str) -> tuple[dict[str, bytes], dict]:
    """What the per-skill path writes: get_graph to enumerate, then get_skill_files per
    skill and get_agent_files per agent, each file written as the content it returns,
    decoded where it says base64. Also the install line get_install_command returns
    for the same harness."""
    tree: dict[str, bytes] = {}
    async with (
        streamable_http_client(f"{base_url}/mcp") as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        nodes = _tool_json(await session.call_tool("get_graph", {}))["nodes"]
        for name in sorted(n["label"] for n in nodes if n["kind"] == "skill"):
            served = _tool_json(await session.call_tool("get_skill_files", {"name": name}))
            for f in served["files"]:
                tree[f"skills/{served['name']}/{f['path']}"] = _decoded(f)
        for name in sorted(n["label"] for n in nodes if n["kind"] == "agent"):
            served = _tool_json(
                await session.call_tool("get_agent_files", {"name": name, "runtime": runtime})
            )
            for agent in served["agents"]:
                tree[f"agents/{agent['filename']}"] = agent["content"].encode("utf-8")
        command = _tool_json(await session.call_tool("get_install_command", {"runtime": runtime}))
    return tree, command


def _skill_sources(root: Path) -> dict[str, Path]:
    """Each corpus skill's folder by name, as the repository finds them."""
    paths = list((root / "skills").glob("*/SKILL.md")) + list(
        root.glob("galaxies/*/skills/*/SKILL.md")
    )
    return {p.parent.name: p.parent for p in paths}


def _assert_matches_per_skill(written: dict[str, bytes], per_skill: dict[str, bytes]) -> None:
    """Every file byte-identical to what the per-skill path writes, binary ones included."""
    assert written.keys() == per_skill.keys(), "the same files, no more and no fewer"
    for path, data in sorted(written.items()):
        assert data == per_skill[path], f"{path} differs from the per-skill path"


class TestTheBundle:
    @intent("INT-INSTALL-001")
    @pytest.mark.anyio
    @pytest.mark.skipif(
        not all(shutil.which(tool) for tool in ("pwsh", "tar")),
        reason="the PowerShell install line needs pwsh and tar",
    )
    async def test_codex_powershell_command_installs_into_its_overridden_homes(
        self, corpus: _Corpus, tmp_path: Path
    ) -> None:
        """Regression #56: run the returned Codex line through the HTTP download
        and real installer, with paths containing spaces and no symlink setup."""
        installed = tmp_path / "installed homes"
        skills, agents = installed / "skills", installed / "agents"
        args = " --codex-skills-dir '" + str(skills).replace("'", "''") + "'"
        args += " --codex-agents-dir '" + str(agents).replace("'", "''") + "'"
        env = {
            **os.environ,
            "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        }
        with _Server(_container(corpus.root, tmp_path)) as srv:
            per_skill, command = await _per_skill_tree(srv.base_url, "codex")
            run = subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command["powershell"] + args],
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
        assert run.returncode == 0, run.stdout + run.stderr
        written = {f"skills/{k}": v for k, v in _files(skills).items()}
        written.update({f"agents/{k}": v for k, v in _files(agents).items()})
        _assert_matches_per_skill(written, per_skill)
        assert all(path.suffix == ".toml" for path in agents.iterdir())

    @intent("INT-INSTALL-001", "INT-MCP-003")
    @pytest.mark.anyio
    @pytest.mark.parametrize("runtime", _RUNTIMES)
    async def test_each_harness_bundle_installs_the_files_its_machine_door_serves(
        self, corpus: _Corpus, runtime: str, tmp_path: Path
    ) -> None:
        """Regression #56: Codex bundles must pass the real installer's extension
        checks, and each harness must write to its own skills and agents home."""
        container = _container(corpus.root, tmp_path)
        with _Server(container) as srv:
            per_skill, command = await _per_skill_tree(srv.base_url, runtime)
        installed = tmp_path / "installed"
        skills, agents = installed / "skills", installed / "agents"
        codex_skills, codex_agents = installed / "codex-skills", installed / "codex-agents"
        opencode_agents = installed / "opencode-agents"
        bundle = _unpack(container, runtime, tmp_path / "bundle")
        argv = [
            sys.executable,
            str(bundle / "scripts" / "install_playbook.py"),
            "--runtime-dir",
            str(skills),
            "--agents-dir",
            str(agents),
            "--opencode-agents-dir",
            str(opencode_agents),
            "--codex-skills-dir",
            str(codex_skills),
            "--codex-agents-dir",
            str(codex_agents),
        ]
        run = subprocess.run(argv, capture_output=True, text=True, timeout=180)
        assert run.returncode == 0, run.stdout + run.stderr
        target_skills = codex_skills if runtime == "codex" else skills
        target_agents = {"claude-code": agents, "opencode": opencode_agents, "codex": codex_agents}[
            runtime
        ]
        written = {f"skills/{k}": v for k, v in _files(target_skills).items()}
        written.update({f"agents/{k}": v for k, v in _files(target_agents).items()})
        _assert_matches_per_skill(written, per_skill)
        if runtime == "codex":
            assert not skills.exists() and not agents.exists() and not opencode_agents.exists()
            assert all(p.suffix == ".toml" for p in target_agents.iterdir())
            assert command["skills_install_dir_hint"] == "~/.agents/skills/"
            assert command["agents_install_dir_hint"] == "~/.codex/agents/"
            if corpus.real:
                import tomllib

                for path in target_agents.iterdir():
                    agent = tomllib.loads(path.read_text(encoding="utf-8"))
                    assert agent["name"] == path.stem
                    assert agent["description"] and agent["developer_instructions"]
        if corpus.real:
            timestamps = {p: p.stat().st_mtime_ns for p in target_skills.rglob("*") if p.is_file()}
            timestamps.update({p: p.stat().st_mtime_ns for p in target_agents.iterdir()})
            second = subprocess.run(argv, capture_output=True, text=True, timeout=180)
            assert second.returncode == 0, second.stdout + second.stderr
            assert "Restart" not in second.stdout
            assert all(p.stat().st_mtime_ns == stamp for p, stamp in timestamps.items())

    @intent("INT-INSTALL-001")
    @pytest.mark.anyio
    @pytest.mark.parametrize("runtime", _RUNTIMES)
    async def test_the_bundle_carries_what_the_per_skill_path_serves(
        self, corpus: _Corpus, runtime: str, tmp_path: Path
    ) -> None:
        container = _container(corpus.root, tmp_path)
        with _Server(container) as srv:
            per_skill, _ = await _per_skill_tree(srv.base_url, runtime)
        bundle = _unpack(container, runtime, tmp_path / "bundle")
        carried = {f"skills/{k}": v for k, v in _files(bundle / "skills").items()}
        carried.update({f"agents/{k}": v for k, v in _files(bundle / "agents").items()})

        _assert_matches_per_skill(carried, per_skill)
        if not corpus.real:
            binary = "skills/gamma-skill/assets/template.bin"
            assert carried[binary] == per_skill[binary] == _BINARY
        sources = _skill_sources(corpus.root)
        for path in carried:
            kind, name, *rest = path.split("/")
            if kind == "skills":
                source = sources[name].joinpath(*rest)
                assert _executable(bundle / path) == _executable(source), f"{path} mode"

        installer_source = (corpus.root / "scripts" / "install_playbook.py").read_bytes()
        assert (bundle / "scripts" / "install_playbook.py").read_bytes() == installer_source
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["runtime"] == runtime
        assert sorted(f["path"] for f in manifest["files"]) == sorted(carried)

    @intent("INT-INSTALL-001")
    @pytest.mark.anyio
    @pytest.mark.skipif(
        not all(shutil.which(tool) for tool in ("sh", "curl", "tar")),
        reason="the POSIX install line needs sh, curl, and tar",
    )
    async def test_one_shell_call_runs_the_bundled_installer(
        self, corpus: _Corpus, tmp_path: Path
    ) -> None:
        container = _container(corpus.root, tmp_path)
        home = tmp_path / "home"
        home.mkdir()
        env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
        with _Server(container) as srv:
            per_skill, command = await _per_skill_tree(srv.base_url, "claude-code")
            runs = [
                subprocess.run(
                    ["sh", "-c", command["posix"] + extra],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                for extra in ("", " --prune")
            ]
        for run in runs:
            assert run.returncode == 0, run.stderr
            assert run.stderr == ""
        written = {f"skills/{k}": v for k, v in _files(home / ".claude" / "skills").items()}
        written.update({f"agents/{k}": v for k, v in _files(home / ".claude" / "agents").items()})
        _assert_matches_per_skill(written, per_skill)
        if not corpus.real:
            files = len(per_skill)
            assert runs[0].stdout == (
                f"stand-in installer: {files} file(s) from the bundle for claude-code\n"
            )
            assert runs[1].stdout.endswith("with --prune\n"), "flags reach the installer"
            return
        first, second = (run.stdout.splitlines() for run in runs)
        assert first[0].startswith("playbook toolchain from the studio bundle ")
        assert first[-1] == "Restart the session to load the new and updated skills and agents."
        assert "Restart" not in runs[1].stdout, "a second run with no change writes nothing"
        assert len(runs[0].stdout) < 20_000, "a summary, never the files"

    @intent("INT-INSTALL-001")
    @pytest.mark.anyio
    @pytest.mark.skipif(
        not all(shutil.which(tool) for tool in ("pwsh", "tar")),
        reason="the PowerShell install line needs pwsh and tar",
    )
    async def test_the_powershell_line_runs_it_too(self, corpus: _Corpus, tmp_path: Path) -> None:
        """Under a caller that turns every error into a stop, and with a python3 on
        PATH that only complains on stderr (as the Store's stub does), the line still
        finds a working Python and runs the bundle's installer with its arguments."""
        stub = tmp_path / "bin"
        stub.mkdir()
        (stub / "python3").write_text("#!/bin/sh\necho 'Python was not found' >&2\nexit 9009\n")
        (stub / "python3").chmod(0o755)
        (stub / "python").symlink_to(sys.executable)
        home = tmp_path / "home"
        home.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(tmp_path / "xdg"),
            "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        }
        with _Server(_container(corpus.root, tmp_path)) as srv:
            per_skill, command = await _per_skill_tree(srv.base_url, "opencode")
            strict = "; ".join(
                (
                    "$ErrorActionPreference = 'Stop'",
                    "$PSNativeCommandUseErrorActionPreference = $true",
                    command["powershell"] + " --prune",
                )
            )
            run = subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command", strict],
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stderr == ""
        written = {f"skills/{k}": v for k, v in _files(home / ".claude" / "skills").items()}
        written.update(
            {f"agents/{k}": v for k, v in _files(tmp_path / "xdg" / "opencode" / "agents").items()}
        )
        _assert_matches_per_skill(written, per_skill)
        if corpus.real:
            assert run.stdout.startswith("playbook toolchain from the studio bundle ")
        else:
            assert run.stdout.endswith("for opencode with --prune\n"), "flags reach it"

    @intent("INT-INSTALL-001")
    def test_the_bundled_installer_runs_on_the_floor_interpreter(self, tmp_path: Path) -> None:
        """The client runs the installer the bundle carries, under whatever Python it
        has: run it from the studio's bundle of the real corpus, with --prune, under
        the oldest Python the install scripts accept, which carries no PyYAML."""
        floor, checkout = os.environ.get(_FLOOR_ENV), os.environ.get(_CHECKOUT_ENV)
        if not (floor and checkout):
            pytest.skip(f"set {_FLOOR_ENV} and {_CHECKOUT_ENV} to run the real installer at 3.8")
        version = subprocess.run(
            [floor, "-c", "import sys; print(sys.version_info[:2] == (3, 8))"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert version.stdout.strip() == "True", f"{floor} is not Python 3.8"
        container = _container(Path(checkout), tmp_path)
        skills, agents = tmp_path / "skills", tmp_path / "agents"
        (skills / "stale-skill").mkdir(parents=True)
        for runtime in _RUNTIMES:
            bundle = _unpack(container, runtime, tmp_path / runtime)
            argv = ["--runtime-dir", str(skills), "--agents-dir", str(agents / "claude")]
            argv += ["--opencode-agents-dir", str(agents / "opencode"), "--prune"]
            argv += ["--codex-skills-dir", str(skills), "--codex-agents-dir", str(agents / "codex")]
            for _ in range(2):
                run = subprocess.run(
                    [floor, str(bundle / "scripts" / "install_playbook.py"), *argv],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                assert run.returncode == 0, run.stderr
            assert "Restart" not in run.stdout
        assert not (skills / "stale-skill").exists()
        assert (agents / "claude" / "reviewer.md").is_file()
        assert (agents / "opencode" / "reviewer.md").is_file()
        assert (agents / "codex" / "reviewer.toml").is_file()


class TestAPulledPlaybook:
    @intent("INT-INSTALL-001")
    def test_the_next_bundle_carries_the_pulled_installer_and_its_renderings(
        self, playbook_root: Path, tmp_path: Path
    ) -> None:
        """The clone is pulled in place while the studio runs: a bundle built after the
        installer changed carries the new file and agents rendered by it."""
        container = _container(playbook_root, tmp_path)
        first = container.get_install_bundle().execute(runtime="claude-code")
        script = playbook_root / installer.INSTALLER
        script.write_text(
            script.read_text(encoding="utf-8").replace(
                "rendered-by-installer: ", "rendered-by-the-pulled-installer: "
            ),
            encoding="utf-8",
        )

        bundle = container.get_install_bundle().execute(runtime="claude-code")

        assert first.installer != bundle.installer == script.read_bytes()
        agents = [f.data.decode("utf-8") for f in bundle.files if f.path.startswith("agents/")]
        assert agents
        assert all("rendered-by-the-pulled-installer: claude-shape" in a for a in agents)


class TestThePerSkillPath:
    @intent("INT-MCP-005", "INT-MCP-003")
    @pytest.mark.anyio
    async def test_install_hints_and_filenames_follow_the_installers_runtime_metadata(
        self, playbook_root: Path, tmp_path: Path
    ) -> None:
        """Regression #56: pulling different runtime hints changes served hints;
        Codex gets native filenames even when all renderings are requested."""
        script = playbook_root / installer.INSTALLER
        script.write_text(
            script.read_text(encoding="utf-8").replace(
                "~/.agents/skills/", "~/custom/codex-skills/"
            ),
            encoding="utf-8",
        )
        with _Server(_container(playbook_root, tmp_path)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                agents = _tool_json(
                    await session.call_tool("get_agent_files", {"name": "alpha-agent"})
                )["agents"]
                served = {
                    runtime: _tool_json(
                        await session.call_tool(
                            "get_skill_files", {"name": "do-alpha", "runtime": runtime}
                        )
                    )
                    for runtime in _RUNTIMES
                }
                default = _tool_json(
                    await session.call_tool("get_skill_files", {"name": "do-alpha"})
                )
                command = _tool_json(
                    await session.call_tool("get_install_command", {"runtime": "codex"})
                )
                unknown = await session.call_tool(
                    "get_skill_files", {"name": "do-alpha", "runtime": "emacs"}
                )
        assert {a["runtime"]: a["filename"] for a in agents} == {
            "claude-code": "alpha-agent.md",
            "opencode": "alpha-agent.md",
            "codex": "alpha-agent.toml",
        }
        assert served["codex"]["install_dir_hint"] == "~/custom/codex-skills/do-alpha/"
        for runtime in ("claude-code", "opencode"):
            assert served[runtime]["install_dir_hint"] == "~/.claude/skills/do-alpha/"
        assert default == served["claude-code"]
        assert command["skills_install_dir_hint"] == "~/custom/codex-skills/"
        assert unknown.isError

    @intent("INT-MCP-005")
    @pytest.mark.anyio
    async def test_every_skill_file_round_trips_byte_for_byte(
        self, corpus: _Corpus, tmp_path: Path
    ) -> None:
        """Every file of every skill, fetched through get_skill_files and decoded as the
        response says, equals the corpus byte for byte. Binary files travel base64."""
        sources = _skill_sources(corpus.root)
        with _Server(_container(corpus.root, tmp_path)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                served = {
                    name: _tool_json(await session.call_tool("get_skill_files", {"name": name}))
                    for name in sorted(sources)
                }
                encoded = [
                    (name, f)
                    for name, response in served.items()
                    for f in response["files"]
                    if f.get("encoding") == "base64"
                ]
                single = [
                    await session.call_tool("get_skill_file", {"name": n, "rel_path": f["path"]})
                    for n, f in encoded
                ]
                first = sorted(sources)[0]
                text = await session.call_tool(
                    "get_skill_file", {"name": first, "rel_path": "SKILL.md"}
                )

        for name, response in served.items():
            on_disk = _files(sources[name])
            written = {f["path"]: _decoded(f) for f in response["files"]}
            assert written.keys() == on_disk.keys(), name
            for path, data in written.items():
                assert data == on_disk[path], f"{name}/{path} differs from the corpus"
        assert [r.structuredContent["result"] for r in single] == [f for _, f in encoded]
        skill_md = (sources[first] / "SKILL.md").read_bytes().decode("utf-8")
        assert text.content[0].text == skill_md, "a UTF-8 file comes back as its text"
        assert text.structuredContent == {"result": skill_md}
        assert encoded, "the corpus carries a file that only base64 can carry"
        if not corpus.real:
            assert [(n, f["path"]) for n, f in encoded] == [("gamma-skill", "assets/template.bin")]

    @intent("INT-MCP-005")
    @pytest.mark.anyio
    async def test_the_tool_descriptions_tell_the_client_to_decode(
        self, playbook_root: Path, tmp_path: Path
    ) -> None:
        with _Server(_container(playbook_root, tmp_path)) as srv:
            async with (
                streamable_http_client(f"{srv.base_url}/mcp") as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = {t.name: t.description or "" for t in (await session.list_tools()).tools}
        for name in ("get_skill_file", "get_skill_files"):
            assert '"encoding": "base64"' in tools[name], name
            assert "decode" in tools[name], name


class TestNoInstallLogicHere:
    @intent("INT-INSTALL-002")
    def test_the_install_scripts_only_launch_the_bundled_installer(self) -> None:
        """The studio serves a launcher and a bundle; every rule about what gets
        written is the playbook installer's, which the bundle carries."""
        shipped = sorted(p.name for p in _INSTALLER_DIR.iterdir() if p.is_file())
        assert shipped == ["__init__.py", "install.ps1", "install.sh"]
        sh = (_INSTALLER_DIR / "install.sh").read_text(encoding="utf-8").splitlines()
        assert sh[-1] == '"$python" "$work/bundle/scripts/install_playbook.py" "$@"'
        ps1 = (_INSTALLER_DIR / "install.ps1").read_text(encoding="utf-8")
        assert "(Join-Path (Join-Path $bundle 'scripts') 'install_playbook.py') @args" in ps1
        assert installer.INSTALLER == "scripts/install_playbook.py"

    @intent("INT-INSTALL-002")
    def test_nothing_in_the_studio_names_the_installers_former_name(self) -> None:
        """Code, CI, claims and current docs name one installer. A superseded decision
        record keeps the words it was decided in."""
        former = "_".join(("install", "skills")) + ".py"
        tops = ("studio-backend", "studio-frontend/src", "docs/src", "devops", "k8s", ".github")
        files = [p for p in _REPO.iterdir() if p.is_file()]
        files += [p for top in tops for p in (_REPO / top).rglob("*") if p.is_file()]
        suffixes = {".py", ".ts", ".tsx", ".md", ".mdx", ".sh", ".ps1", ".yaml", ".yml", ".toml"}
        offenders = [
            str(p.relative_to(_REPO))
            for p in files
            if "node_modules" not in p.parts
            and "__pycache__" not in p.parts
            and p.suffix in suffixes
            and former in (text := p.read_text(encoding="utf-8", errors="replace"))
            and "adr_status: Superseded" not in text
        ]
        assert offenders == []
