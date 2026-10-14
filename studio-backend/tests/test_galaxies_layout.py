"""The repository reads one universe: root documents and galaxies/<name>/ shelves."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_intent import intent

from studio.adapters.outbound.playbook_fs.fs_playbook_repository import FsPlaybookRepository
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.model.edge_kind import EdgeKind

_REF_ALPHA = """---
domain: language
---

# REF: Alpha

> Alpha conventions.

---

## 1. Rules

Always be Alpha.
"""

_REF_GAMMA = """---
domain: practice
---

# REF: Gamma

> Gamma earned knowledge.

---

## 1. Guidance

Borrow from `REF-Alpha.md` freely.
"""

_PLAYBOOK = """# AI Playbook

The universe index. The craft shelf routes via `REF-Alpha.md`.
"""

_GALAXY_GAMMA = """# Galaxy: Gamma

> The gamma shelf.

## Task Routing - load only what you need

| Task | Read These REFs |
| ---- | --------------- |
| Gamma work | `REF-Gamma.md` |
"""

_SKILL_ALPHA = """---
name: do-alpha
description: Do the alpha thing.
refs:
  - REF-Alpha
---

# Do alpha
"""

_SKILL_GAMMA = """---
name: do-gamma
description: Do the gamma thing.
refs:
  - REF-Gamma
---

# Do gamma
"""

_DOOR_GAMMA = """---
name: gamma-door
galaxy: gamma
refs:
  - REF-Gamma
---

# MCP: gamma-door

> Knock here to act on gamma things.

The gamma system's door.
"""

_AGENT_GAMMA = """---
name: gamma-agent
title: The gamma agent
description: "Reviews gamma work it had no hand in; hand it a gamma artifact."
galaxy: gamma
refs:
  - REF-Gamma
  - REF-Alpha
skills:
  - do-gamma
doors:
  - gamma-door
posture:
  permission: plan
  writes: false
  fresh_eyes: true
---

# Agent: The gamma agent

Reviews gamma work it had no hand in. Refuses to edit what it judges.
"""

_NEBULA_ABYSS = """# Nebula: abyss

> UNEARNED. This nebula holds stardust, quarantined from the galaxies.

**Subject**: abyssal survey robotics. **Why then**: a layout fixture.
"""

# A REF-named file INSIDE a nebula: hostile shelving that must stay stardust.
_NEBULA_NOTE_TRAP = """---
type: concept
confidence: low
vote: "2-1"
seats: [builder]
sources:
  - https://example.com/trap
links: []
status: unsmelted
---

# REF-Trap

A REF-named file inside a nebula never reaches the discovery globs.
"""


@pytest.fixture()
def universe_root(tmp_path: Path) -> Path:
    (tmp_path / "AI-PLAYBOOK.md").write_text(_PLAYBOOK, encoding="utf-8")
    (tmp_path / "REF-Alpha.md").write_text(_REF_ALPHA, encoding="utf-8")
    alpha_skill = tmp_path / "skills" / "do-alpha"
    alpha_skill.mkdir(parents=True)
    (alpha_skill / "SKILL.md").write_text(_SKILL_ALPHA, encoding="utf-8")

    gamma = tmp_path / "galaxies" / "gamma"
    gamma.mkdir(parents=True)
    (gamma / "GALAXY.md").write_text(_GALAXY_GAMMA, encoding="utf-8")
    (gamma / "REF-Gamma.md").write_text(_REF_GAMMA, encoding="utf-8")
    gamma_skill = gamma / "skills" / "do-gamma"
    gamma_skill.mkdir(parents=True)
    (gamma_skill / "SKILL.md").write_text(_SKILL_GAMMA, encoding="utf-8")
    mcps = gamma / "mcps"
    mcps.mkdir()
    (mcps / "gamma-door.md").write_text(_DOOR_GAMMA, encoding="utf-8")
    (gamma / "rags").mkdir()
    agents = gamma / "agents"
    agents.mkdir()
    (agents / "gamma-agent.md").write_text(_AGENT_GAMMA, encoding="utf-8")

    abyss = tmp_path / "nebulae" / "abyss"
    abyss.mkdir(parents=True)
    (abyss / "NEBULA.md").write_text(_NEBULA_ABYSS, encoding="utf-8")
    (abyss / "REF-Trap.md").write_text(_NEBULA_NOTE_TRAP, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def repo(universe_root: Path) -> FsPlaybookRepository:
    return FsPlaybookRepository(universe_root)


def test_list_refs_spans_root_and_galaxies(repo: FsPlaybookRepository) -> None:
    refs = repo.list_refs()
    assert [r.name for r in refs] == ["REF-Alpha", "REF-Gamma"]
    assert [r.galaxy for r in refs] == [None, "gamma"]


def test_get_ref_resolves_by_name_into_a_galaxy(repo: FsPlaybookRepository) -> None:
    ref = repo.get_ref(name="REF-Gamma")
    assert ref.galaxy == "gamma"
    assert ref.title == "Gamma"
    with pytest.raises(EntityNotFoundError):
        repo.get_ref(name="REF-Missing")


def test_list_skills_spans_root_and_galaxies(repo: FsPlaybookRepository) -> None:
    skills = repo.list_skills()
    assert [s.name for s in skills] == ["do-alpha", "do-gamma"]
    assert [s.galaxy for s in skills] == [None, "gamma"]


def test_get_skill_resolves_by_name_into_a_galaxy(repo: FsPlaybookRepository) -> None:
    skill = repo.get_skill(name="do-gamma")
    assert skill.galaxy == "gamma"
    assert skill.refs == ("REF-Gamma",)


def test_edges_span_hubs_refs_and_skills(repo: FsPlaybookRepository) -> None:
    edges = {(e.source, e.target, e.kind) for e in repo.list_edges()}
    assert ("AI-PLAYBOOK", "REF-Alpha", EdgeKind.PLAYBOOK_TO_REF) in edges
    assert ("AI-PLAYBOOK", "REF-Gamma", EdgeKind.PLAYBOOK_TO_REF) in edges
    assert ("REF-Gamma", "REF-Alpha", EdgeKind.REF_TO_REF) in edges
    assert ("do-gamma", "REF-Gamma", EdgeKind.SKILL_TO_REF) in edges


def test_write_ref_document_edits_in_place(repo: FsPlaybookRepository, universe_root: Path) -> None:
    updated = _REF_GAMMA.replace("Gamma earned knowledge.", "Gamma earned knowledge, revised.")
    ref = repo.write_ref_document(ref_name="REF-Gamma", raw=updated)
    assert ref.summary == "Gamma earned knowledge, revised."
    on_disk = (universe_root / "galaxies" / "gamma" / "REF-Gamma.md").read_text(encoding="utf-8")
    assert "revised" in on_disk
    assert not (universe_root / "REF-Gamma.md").exists()


def test_skill_files_resolve_inside_a_galaxy(repo: FsPlaybookRepository) -> None:
    content = repo.read_skill_file(name="do-gamma", rel_path="SKILL.md")
    assert "Do gamma" in content


def test_doors_are_parsed_from_their_seats(repo: FsPlaybookRepository) -> None:
    doors = repo.list_doors()
    assert [d.name for d in doors] == ["gamma-door"]
    door = doors[0]
    assert str(door.kind) == "mcp"
    assert door.galaxy == "gamma"
    assert door.refs == ("REF-Gamma",)
    assert door.summary == "Knock here to act on gamma things."


def test_door_edges_reach_their_suns(repo: FsPlaybookRepository) -> None:
    edges = {(e.source, e.target, str(e.kind)) for e in repo.list_edges()}
    assert ("gamma-door", "REF-Gamma", "door-to-ref") in edges


def test_agents_are_parsed_from_their_seats(repo: FsPlaybookRepository) -> None:
    agents = repo.list_agents()
    assert [a.name for a in agents] == ["gamma-agent"]
    agent = agents[0]
    assert agent.title == "The gamma agent"
    assert agent.galaxy == "gamma"
    assert agent.refs == ("REF-Gamma", "REF-Alpha")
    assert agent.skills == ("do-gamma",)
    assert agent.doors == ("gamma-door",)
    assert agent.posture.permission == "plan"
    assert agent.posture.writes is False
    assert agent.posture.fresh_eyes is True
    assert agent.appearance is None
    assert agent.description == "Reviews gamma work it had no hand in; hand it a gamma artifact."
    assert agent.summary == agent.description


def test_get_agent_resolves_by_name_into_a_galaxy(repo: FsPlaybookRepository) -> None:
    agent = repo.get_agent(name="gamma-agent")
    assert agent.galaxy == "gamma"
    with pytest.raises(EntityNotFoundError):
        repo.get_agent(name="missing-agent")


def test_agent_edges_reach_suns_skills_and_doors(repo: FsPlaybookRepository) -> None:
    edges = {(e.source, e.target, str(e.kind)) for e in repo.list_edges()}
    assert ("gamma-agent", "REF-Gamma", "agent-to-ref") in edges
    assert ("gamma-agent", "REF-Alpha", "agent-to-ref") in edges
    assert ("gamma-agent", "do-gamma", "agent-to-skill") in edges
    assert ("gamma-agent", "gamma-door", "agent-to-door") in edges


def test_agent_edges_preserve_frontmatter_order(repo: FsPlaybookRepository) -> None:
    """The first agent-to-ref edge is the agent's HOME sun (REF-Universe §3),
    so authored refs order must survive into the graph."""
    for agent in repo.list_agents():
        edge_targets = [
            e.target
            for e in repo.list_edges()
            if e.source == agent.name and str(e.kind) == "agent-to-ref"
        ]
        expected = [r for r in agent.refs if r in {x.name for x in repo.list_refs()}]
        assert edge_targets == expected


def test_get_galaxy_parses_the_routing_doc(repo: FsPlaybookRepository) -> None:
    galaxy = repo.get_galaxy(name="gamma")
    assert galaxy.name == "gamma"
    assert galaxy.title == "Galaxy: Gamma"
    assert any("Gamma work" in s.body for s in galaxy.sections)
    with pytest.raises(EntityNotFoundError):
        repo.get_galaxy(name="missing")


def test_skill_edges_preserve_frontmatter_order(repo: FsPlaybookRepository) -> None:
    """The first skill-to-ref edge is the skill's HOME sun (REF-Universe §3),
    so authored refs order must survive into the graph."""
    for skill in repo.list_skills():
        edge_targets = [
            e.target
            for e in repo.list_edges()
            if e.source == skill.name and str(e.kind) == "skill-to-ref"
        ]
        expected = [r for r in skill.refs if r in {x.name for x in repo.list_refs()}]
        assert edge_targets == expected


@intent("INT-QUAR-001")
def test_discovery_never_reaches_into_nebulae(repo: FsPlaybookRepository) -> None:
    """nebulae/ is structurally invisible to every earned-content scan, even
    when a nebula shelves a REF-named file."""
    assert [r.name for r in repo.list_refs()] == ["REF-Alpha", "REF-Gamma"]
    assert [s.name for s in repo.list_skills()] == ["do-alpha", "do-gamma"]
    assert [d.name for d in repo.list_doors()] == ["gamma-door"]
    assert [a.name for a in repo.list_agents()] == ["gamma-agent"]
    edges = repo.list_edges()
    endpoints = {e.source for e in edges} | {e.target for e in edges}
    assert "REF-Trap" not in endpoints
    assert "abyss" not in endpoints


def test_nebulae_parse_from_their_own_zone(repo: FsPlaybookRepository) -> None:
    [summary] = repo.list_nebulae()
    assert summary.territory == "abyss"
    assert summary.subject == "abyssal survey robotics"
    assert (summary.note_count, summary.unsmelted, summary.taken, summary.burned) == (1, 1, 0, 0)

    nebula = repo.get_nebula(territory="abyss")
    assert nebula.subject == "abyssal survey robotics"
    assert "UNEARNED" in nebula.raw
    [note] = nebula.notes
    assert note.name == "REF-Trap"
    assert note.note_type == "concept"
    assert note.vote == "2-1"
    assert note.status == "unsmelted"
    assert "discovery globs" in note.body
    with pytest.raises(EntityNotFoundError):
        repo.get_nebula(territory="missing")


def test_nebula_territory_must_be_a_slug(repo: FsPlaybookRepository) -> None:
    """The territory segment never reaches the filesystem join unless it is a
    strict lowercase slug; dots, slashes, and backslashes all 404."""
    for hostile in ("../galaxies", "..\\..", "..", "Abyss", "a/b", "a\\b", ""):
        with pytest.raises(EntityNotFoundError):
            repo.get_nebula(territory=hostile)


def test_get_door_returns_one_door_with_its_raw_document(repo: FsPlaybookRepository) -> None:
    from studio.application.use_cases.get_door import GetDoor

    door = GetDoor(repo).execute(name="gamma-door")
    assert door.name == "gamma-door"
    assert door.galaxy == "gamma"
    assert "Knock here" in door.raw
    with pytest.raises(EntityNotFoundError):
        GetDoor(repo).execute(name="missing-door")
