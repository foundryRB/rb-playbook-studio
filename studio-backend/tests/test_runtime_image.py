"""The runtime image carries every tool the playbook's gates call, and the docs say so.

Attests INT-GATE-004. The studio's gate is the playbook's own suite; a tool the
runtime stage lacks fails that suite, and every gated edit is rolled back.
"""

from __future__ import annotations

import re
from pathlib import Path

from pytest_intent import intent

_ROOT = Path(__file__).resolve().parents[2]
_DOCKERFILE = _ROOT / "devops/Dockerfile"
_PAGE = _ROOT / "docs/src/content/docs/architecture/system-context.md"
_SECTION = "## The app image"


def _stages() -> list[tuple[str, str, list[tuple[str, str]]]]:
    """(base image, stage name, instructions) per FROM, continuation lines joined."""
    text = _DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    stages: list[tuple[str, str, list[tuple[str, str]]]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, args = line.partition(" ")
        keyword, args = keyword.upper(), " ".join(args.split())
        if keyword == "FROM":
            match = re.fullmatch(r"(?:--\S+ )*(\S+)(?: as (\S+))?", args, re.IGNORECASE)
            assert match, f"unparsed FROM {args!r}"
            stages.append((match.group(1), match.group(2) or "", []))
        else:
            stages[-1][2].append((keyword, args))
    return stages


def _runtime() -> list[tuple[str, str]]:
    stages = _stages()
    assert stages, "the Dockerfile has no stage"
    return stages[-1][2]


def _node_copy_index(runtime: list[tuple[str, str]]) -> int:
    """Where the runtime stage takes node from the Node build stage onto PATH."""
    node_stages = {name for base, name, _ in _stages()[:-1] if base.startswith("node:") and name}
    for i, (keyword, args) in enumerate(runtime):
        match = re.fullmatch(r"--from=(\S+) (\S+/node) (/usr/local/bin/(?:node)?)", args)
        if keyword == "COPY" and match and match.group(1) in node_stages:
            return i
    raise AssertionError(f"the runtime stage takes no node binary from a Node stage {node_stages}")


@intent("INT-GATE-004")
def test_the_runtime_stage_installs_git_and_the_gates_extra() -> None:
    """INT-GATE-004: git and the gates extra are in the image the studio serves from."""
    runs = [args for keyword, args in _runtime() if keyword == "RUN"]
    assert any(re.search(r"apt-get install [^&;]*\bgit\b", run) for run in runs), runs
    assert any(re.search(r"pip install [^&;]*\[gates\]", run) for run in runs), runs


@intent("INT-GATE-004")
def test_the_runtime_stage_runs_the_node_it_takes_from_the_build_stage() -> None:
    """INT-GATE-004: node is copied onto PATH and run, so a missing node fails the build."""
    runtime = _runtime()
    taken = _node_copy_index(runtime)
    assert any(
        keyword == "RUN" and args.startswith("node ") for keyword, args in runtime[taken + 1 :]
    ), "the runtime stage never runs node after taking it, so its absence would not fail the build"


@intent("INT-GATE-004")
def test_the_docs_page_names_every_runtime_dependency() -> None:
    """INT-GATE-004: the page that lists the image's runtime dependencies names each one."""
    text = _PAGE.read_text(encoding="utf-8")
    section = text[text.index(_SECTION) :].split("\n## ", 1)[0]
    stated = {label.lower() for label in re.findall(r"^- \*\*([^*]+)\*\*", section, re.MULTILINE)}
    missing = {"git", "the gates extra", "node"} - stated
    assert not missing, f"{_PAGE.name} does not name {sorted(missing)} under {_SECTION!r}"
