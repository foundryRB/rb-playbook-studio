"""HTTP integration tests: real app, real file I/O against a synthetic playbook."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest_intent import intent

from studio import __version__

_GENERATED_LINE = "the sync wrote this\n"

# Stands in for scripts/sync_backlinks.py: it rewrites a REF the way the real
# generator does, so a test can see whether the write path ran it and whether a
# rollback took its output back out.
_SYNC_REWRITES_A_REF = (
    "from pathlib import Path\n"
    "ref = Path('REF-Alpha.md')\n"
    f"ref.write_text(ref.read_text(encoding='utf-8') + {_GENERATED_LINE!r}, encoding='utf-8')\n"
)

# The real script exits non-zero on the malformed frontmatter the gates exist to
# reject, which is the case that must read as a refusal rather than a crash.
_SYNC_REFUSES = (
    "import sys\n"
    "sys.stderr.write('do-alpha/SKILL.md has no frontmatter block\\n')\n"
    "sys.exit(1)\n"
)


def _plant_sync_script(playbook_root: Path, body: str) -> None:
    (playbook_root / "scripts" / "sync_backlinks.py").write_text(body, encoding="utf-8")


class TestSystem:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_reports_the_running_image_tag(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The chart injects the promoted tag as $APP_VERSION, so an external
        observer reading /api/health learns which release is serving. The package
        constant would be a hardcoded string, which is not freshness."""
        monkeypatch.setenv("APP_VERSION", "1.22.0")
        assert client.get("/api/health").json()["version"] == "1.22.0"

    def test_health_falls_back_to_the_package_version(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A local run has no injected tag; health still answers."""
        monkeypatch.delenv("APP_VERSION", raising=False)
        assert client.get("/api/health").json()["version"] == __version__


class TestGraph:
    @intent("INT-GRAPH-001")
    def test_graph_contains_playbook_refs_skills_and_agents(self, client: TestClient) -> None:
        resp = client.get("/api/graph")
        assert resp.status_code == 200
        graph = resp.json()
        ids = {n["id"] for n in graph["nodes"]}
        assert {"AI-PLAYBOOK", "REF-Alpha", "REF-Beta", "do-alpha", "alpha-agent"} <= ids

    @intent("INT-GRAPH-001")
    def test_graph_has_every_authored_edge_kind(self, client: TestClient) -> None:
        kinds = {e["kind"] for e in client.get("/api/graph").json()["edges"]}
        assert kinds == {
            "playbook-to-ref",
            "ref-to-ref",
            "skill-to-ref",
            "agent-to-ref",
            "agent-to-skill",
        }

    @intent("INT-GRAPH-001")
    def test_ref_nodes_carry_their_domain(self, client: TestClient) -> None:
        nodes = {n["id"]: n for n in client.get("/api/graph").json()["nodes"]}
        assert nodes["REF-Alpha"]["domain"] == "language"
        assert nodes["AI-PLAYBOOK"]["domain"] is None

    @intent("INT-GRAPH-001")
    def test_nodes_carry_summaries(self, client: TestClient) -> None:
        nodes = {n["id"]: n for n in client.get("/api/graph").json()["nodes"]}
        assert nodes["REF-Alpha"]["summary"] == "Alpha conventions."
        assert nodes["do-alpha"]["summary"].startswith("Do the alpha thing.")
        assert nodes["alpha-agent"]["summary"] == (
            "Runs the alpha thing end to end; hand it alpha work."
        )

    @intent("INT-GRAPH-001")
    def test_agent_nodes_are_their_own_kind(self, client: TestClient) -> None:
        nodes = {n["id"]: n for n in client.get("/api/graph").json()["nodes"]}
        agent = nodes["alpha-agent"]
        assert agent["kind"] == "agent"
        assert agent["galaxy"] == "craft"
        edges = {
            (e["source"], e["target"], e["kind"])
            for e in client.get("/api/graph").json()["edges"]
        }
        assert ("alpha-agent", "REF-Alpha", "agent-to-ref") in edges
        assert ("alpha-agent", "do-alpha", "agent-to-skill") in edges


_STARDUST_NAMES = {"deep-sea-mining", "nodule-harvesters", "isa-regulation", "seat-operator"}


class TestNebulae:
    @intent("INT-NEBULA-001")
    def test_nebulae_are_listed_with_status_counts(self, client: TestClient) -> None:
        resp = client.get("/api/nebulae")
        assert resp.status_code == 200
        [nebula] = resp.json()
        assert nebula["territory"] == "deep-sea-mining"
        assert nebula["subject"] == "deep sea mining operations software"
        assert nebula["note_count"] == 3
        assert (nebula["unsmelted"], nebula["taken"], nebula["burned"]) == (2, 1, 0)

    @intent("INT-NEBULA-001")
    def test_nebula_detail_serves_roster_frontmatter_and_bodies(self, client: TestClient) -> None:
        resp = client.get("/api/nebulae/deep-sea-mining")
        assert resp.status_code == 200
        nebula = resp.json()
        assert nebula["territory"] == "deep-sea-mining"
        assert "UNEARNED" in nebula["raw"]
        notes = {n["name"]: n for n in nebula["notes"]}
        assert set(notes) == {"nodule-harvesters", "isa-regulation", "seat-operator"}
        tool = notes["nodule-harvesters"]
        assert tool["type"] == "tool"
        assert tool["confidence"] == "high"
        assert tool["vote"] == "3-0"
        assert tool["seats"] == ["operator", "incumbent"]
        assert tool["sources"] == ["https://example.com/harvesters"]
        assert tool["links"] == ["isa-regulation"]
        assert tool["status"] == "unsmelted"
        assert "[[isa-regulation]]" in tool["body"]
        assert notes["seat-operator"]["vote"] is None
        assert notes["seat-operator"]["confidence"] == "derived"

    def test_unknown_nebula_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/nebulae/no-such-territory")
        assert resp.status_code == 404
        assert resp.json()["error"] == "EntityNotFoundError"

    def test_traversal_territory_returns_404(self, client: TestClient) -> None:
        """A territory is a strict slug; an encoded backslash (or any other
        non-slug segment) must 404, never touch the filesystem join."""
        for hostile in ("..%5C..%5Cskills", "..%2F..%2Fskills", ".."):
            resp = client.get(f"/api/nebulae/{hostile}")
            assert resp.status_code == 404, hostile

    @intent("INT-NEBULA-001")
    def test_malformed_note_degrades_without_taking_the_roster_down(
        self, client: TestClient, playbook_root: Path
    ) -> None:
        """Stardust is foreign-authored: broken YAML, a non-mapping header, or
        scalar list fields degrade per note; both endpoints stay 200 and the
        healthy territory is untouched."""
        broken = playbook_root / "nebulae" / "broken-territory"
        broken.mkdir(parents=True)
        (broken / "NEBULA.md").write_text(
            "# Nebula: broken-territory\n\n**Subject**: malformed stardust handling.\n",
            encoding="utf-8",
        )
        (broken / "bad-yaml.md").write_text(
            '---\nseats: [operator\nvote: "3-0\n---\n\nThe claim survives its broken header.\n',
            encoding="utf-8",
        )
        (broken / "list-frontmatter.md").write_text(
            "---\n- not\n- a\n- mapping\n---\n\nA list where a mapping belongs.\n",
            encoding="utf-8",
        )
        (broken / "scalar-fields.md").write_text(
            "---\ntype: learning\nconfidence: low\nvote: '1-0'\nseats: operator\n"
            "sources: https://example.com/one\nlinks: bad-yaml\nstatus: unsmelted\n---\n\n"
            "Scalar fields coerce to one-element lists.\n",
            encoding="utf-8",
        )

        listing = client.get("/api/nebulae")
        assert listing.status_code == 200
        by_territory = {n["territory"]: n for n in listing.json()}
        assert by_territory["broken-territory"]["note_count"] == 3
        assert by_territory["deep-sea-mining"]["note_count"] == 3

        detail = client.get("/api/nebulae/broken-territory")
        assert detail.status_code == 200
        notes = {n["name"]: n for n in detail.json()["notes"]}
        bad = notes["bad-yaml"]
        assert bad["type"] == ""
        assert bad["vote"] is None
        assert bad["seats"] == []
        assert "survives its broken header" in bad["body"]
        assert "a mapping belongs" in notes["list-frontmatter"]["body"]
        scalar = notes["scalar-fields"]
        assert scalar["seats"] == ["operator"]
        assert scalar["sources"] == ["https://example.com/one"]
        assert scalar["links"] == ["bad-yaml"]

        good = client.get("/api/nebulae/deep-sea-mining")
        assert good.status_code == 200
        assert len(good.json()["notes"]) == 3


class TestQuarantine:
    @intent("INT-QUAR-001")
    def test_graph_carries_no_nebula_nodes_or_edges(self, client: TestClient) -> None:
        """The fixture corpus holds a populated nebulae/ zone; the graph must not."""
        graph = client.get("/api/graph").json()
        assert not {n["id"] for n in graph["nodes"]} & _STARDUST_NAMES
        assert all("nebula" not in n["kind"] for n in graph["nodes"])
        endpoints = {e["source"] for e in graph["edges"]} | {
            e["target"] for e in graph["edges"]
        }
        assert not endpoints & _STARDUST_NAMES


class TestRefDetail:
    def test_ref_detail_parses_sections(self, client: TestClient) -> None:
        resp = client.get("/api/refs/REF-Alpha")
        assert resp.status_code == 200
        ref = resp.json()
        assert ref["title"] == "Alpha"
        assert ref["summary"] == "Alpha conventions."
        assert [s["number"] for s in ref["sections"]] == [1, 2, 3]

    def test_generated_sections_are_flagged(self, client: TestClient) -> None:
        sections = client.get("/api/refs/REF-Alpha").json()["sections"]
        by_number = {s["number"]: s for s in sections}
        assert by_number[2]["generated"] is True
        assert by_number[3]["generated"] is True
        assert by_number[1]["generated"] is False

    def test_unknown_ref_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/refs/REF-Nope")
        assert resp.status_code == 404
        assert resp.json()["error"] == "EntityNotFoundError"


class TestPlaybook:
    def test_playbook_sections_are_parsed(self, client: TestClient) -> None:
        resp = client.get("/api/playbook")
        assert resp.status_code == 200
        doc = resp.json()
        assert doc["title"] == "AI Playbook"
        titles = [s["title"] for s in doc["sections"]]
        assert "Top Violations - Check EVERY Change" in titles
        violations = next(s for s in doc["sections"] if s["title"].startswith("Top Violations"))
        assert "Do not duplicate" in violations["body"]


class TestGalaxy:
    def test_galaxy_sections_are_parsed(self, client: TestClient) -> None:
        resp = client.get("/api/galaxies/craft")
        assert resp.status_code == 200
        doc = resp.json()
        assert doc["title"] == "Galaxy: craft"
        titles = [s["title"] for s in doc["sections"]]
        assert "Craft Violations - Check EVERY Change" in titles

    def test_an_unknown_galaxy_is_not_found(self, client: TestClient) -> None:
        assert client.get("/api/galaxies/nowhere").status_code == 404

    @intent("INT-GATE-001")
    def test_edit_survives_when_gates_pass(self, client: TestClient) -> None:
        """The case the door exists for: one more entry in the violations list."""
        raw = client.get("/api/galaxies/craft").json()["raw"]
        edited = raw.replace(
            "1. **Do not duplicate.**",
            "1. **Do not duplicate.**\n2. **No em-dashes.**",
        )

        resp = client.put("/api/galaxies/craft", json={"raw": edited})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        after = client.get("/api/galaxies/craft").json()
        violations = next(s for s in after["sections"] if s["title"].startswith("Craft Violations"))
        assert "No em-dashes" in violations["body"]

    @intent("INT-GATE-001")
    def test_edit_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        original = failing_client.get("/api/galaxies/craft").json()["raw"]

        resp = failing_client.put("/api/galaxies/craft", json={"raw": "# Galaxy: craft\n"})
        assert resp.status_code == 422
        assert resp.json()["error"] == "ValidationFailedError"
        assert failing_client.get("/api/galaxies/craft").json()["raw"] == original


class TestClaims:
    def test_claims_are_listed(self, client: TestClient) -> None:
        claims = client.get("/api/claims").json()
        assert [c["claim_id"] for c in claims] == ["INT-001"]
        assert claims[0]["criticality"] == "high"


class TestUpdateSection:
    @intent("INT-GATE-001")
    def test_edit_survives_when_gates_pass(self, client: TestClient) -> None:
        resp = client.put(
            "/api/refs/REF-Alpha/sections/1",
            json={"body": "Always be Alpha, twice. See `REF-Beta.md`."},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        body = client.get("/api/refs/REF-Alpha").json()["sections"][0]["body"]
        assert "twice" in body

    @intent("INT-GATE-001")
    def test_edit_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        original = failing_client.get("/api/refs/REF-Alpha").json()["sections"][0]["body"]
        resp = failing_client.put(
            "/api/refs/REF-Alpha/sections/1",
            json={"body": "This edit must not survive."},
        )
        assert resp.status_code == 422
        assert resp.json()["error"] == "ValidationFailedError"
        assert resp.json()["report"]["ok"] is False
        after = failing_client.get("/api/refs/REF-Alpha").json()["sections"][0]["body"]
        assert after == original

    @intent("INT-GATE-002")
    def test_generated_skill_section_is_immutable(self, client: TestClient) -> None:
        resp = client.put(
            "/api/refs/REF-Alpha/sections/2",
            json={"body": "hand edit"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"] == "GeneratedSectionError"

    @intent("INT-GATE-002")
    def test_generated_agent_section_is_immutable(self, client: TestClient) -> None:
        resp = client.put(
            "/api/refs/REF-Alpha/sections/3",
            json={"body": "hand edit"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"] == "GeneratedSectionError"

    def test_missing_section_returns_404(self, client: TestClient) -> None:
        resp = client.put("/api/refs/REF-Beta/sections/9", json={"body": "x"})
        assert resp.status_code == 404


class TestUpdateDocument:
    @intent("INT-GATE-001")
    def test_full_rewrite_survives_when_gates_pass(self, client: TestClient) -> None:
        original = client.get("/api/refs/REF-Beta").json()["raw"]
        rewritten = original.replace("## 1. Guidance", "## 1. Guidance (revised)")
        resp = client.put("/api/refs/REF-Beta", json={"raw": rewritten})
        assert resp.status_code == 200
        after = client.get("/api/refs/REF-Beta").json()
        assert after["sections"][0]["title"] == "Guidance (revised)"

    @intent("INT-GATE-001")
    def test_full_rewrite_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        original = failing_client.get("/api/refs/REF-Beta").json()["raw"]
        resp = failing_client.put("/api/refs/REF-Beta", json={"raw": "# REF: Broken\n"})
        assert resp.status_code == 422
        assert failing_client.get("/api/refs/REF-Beta").json()["raw"] == original


class TestCreateRef:
    _PAYLOAD = {
        "name": "REF-Gamma",
        "domain": "practice",
        "title": "Gamma",
        "summary": "Gamma practices.",
    }

    @intent("INT-DERIVE-001")
    def test_create_survives_when_gates_pass(self, client: TestClient) -> None:
        resp = client.post("/api/refs", json=self._PAYLOAD)
        assert resp.status_code == 201
        created = client.get("/api/refs/REF-Gamma").json()
        assert created["domain"] == "practice"
        assert [s["number"] for s in created["sections"]] == [1]

    def test_duplicate_name_returns_409(self, client: TestClient) -> None:
        assert client.post("/api/refs", json=self._PAYLOAD).status_code == 201
        assert client.post("/api/refs", json=self._PAYLOAD).status_code == 409

    def test_bad_name_returns_400(self, client: TestClient) -> None:
        resp = client.post("/api/refs", json={**self._PAYLOAD, "name": "gamma"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "InvalidRefInputError"

    @intent("INT-GATE-001")
    def test_create_is_removed_when_gates_fail(self, failing_client: TestClient) -> None:
        resp = failing_client.post("/api/refs", json=self._PAYLOAD)
        assert resp.status_code == 422
        assert failing_client.get("/api/refs/REF-Gamma").status_code == 404


class TestSkillDocument:
    def test_skill_detail_is_parsed(self, client: TestClient) -> None:
        resp = client.get("/api/skills/do-alpha")
        assert resp.status_code == 200
        skill = resp.json()
        assert skill["refs"] == ["REF-Alpha"]
        assert skill["body"].startswith("# Do alpha")

    @intent("INT-GATE-001")
    def test_skill_rewrite_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        original = failing_client.get("/api/skills/do-alpha").json()["raw"]
        resp = failing_client.put("/api/skills/do-alpha", json={"raw": "broken"})
        assert resp.status_code == 422
        assert failing_client.get("/api/skills/do-alpha").json()["raw"] == original

    @intent("INT-DERIVE-002")
    def test_an_accepted_rewrite_runs_the_playbook_script_over_the_corpus(
        self, client: TestClient, playbook_root: Path
    ) -> None:
        _plant_sync_script(playbook_root, _SYNC_REWRITES_A_REF)
        ref = playbook_root / "REF-Alpha.md"
        before = ref.read_text(encoding="utf-8")
        raw = client.get("/api/skills/do-alpha").json()["raw"]

        resp = client.put("/api/skills/do-alpha", json={"raw": raw})
        assert resp.status_code == 200
        assert ref.read_text(encoding="utf-8") == before + _GENERATED_LINE

    @intent("INT-DERIVE-002")
    def test_a_rejected_rewrite_restores_every_ref_the_sync_rewrote(
        self, failing_client: TestClient, playbook_root: Path
    ) -> None:
        _plant_sync_script(playbook_root, _SYNC_REWRITES_A_REF)
        ref = playbook_root / "REF-Alpha.md"
        before = ref.read_text(encoding="utf-8")

        resp = failing_client.put("/api/skills/do-alpha", json={"raw": "broken"})
        assert resp.status_code == 422
        assert ref.read_text(encoding="utf-8") == before

    @intent("INT-GATE-001")
    def test_a_sync_that_refuses_the_corpus_rolls_back_and_reports(
        self, client: TestClient, playbook_root: Path
    ) -> None:
        """The script rejects what the gates reject, so its refusal is a refusal."""
        _plant_sync_script(playbook_root, _SYNC_REFUSES)
        original = client.get("/api/skills/do-alpha").json()["raw"]

        resp = client.put("/api/skills/do-alpha", json={"raw": "broken"})
        assert resp.status_code == 422
        assert client.get("/api/skills/do-alpha").json()["raw"] == original

    @intent("INT-DERIVE-002")
    def test_an_accepted_agent_rewrite_runs_the_playbook_script(
        self, client: TestClient, playbook_root: Path
    ) -> None:
        _plant_sync_script(playbook_root, _SYNC_REWRITES_A_REF)
        ref = playbook_root / "REF-Alpha.md"
        before = ref.read_text(encoding="utf-8")
        raw = client.get("/api/agents/alpha-agent").json()["raw"]

        resp = client.put("/api/agents/alpha-agent", json={"raw": raw})
        assert resp.status_code == 200
        assert ref.read_text(encoding="utf-8") == before + _GENERATED_LINE

    @intent("INT-DERIVE-002")
    def test_a_rejected_agent_rewrite_restores_every_ref_the_sync_rewrote(
        self, failing_client: TestClient, playbook_root: Path
    ) -> None:
        _plant_sync_script(playbook_root, _SYNC_REWRITES_A_REF)
        ref = playbook_root / "REF-Alpha.md"
        before = ref.read_text(encoding="utf-8")

        resp = failing_client.put("/api/agents/alpha-agent", json={"raw": "broken"})
        assert resp.status_code == 422
        assert ref.read_text(encoding="utf-8") == before


class TestSkillFiles:
    def test_files_are_listed_skill_md_first(self, client: TestClient) -> None:
        files = client.get("/api/skills/do-alpha").json()["files"]
        assert files[0] == "SKILL.md"

    def test_file_content_is_served(self, client: TestClient) -> None:
        resp = client.get("/api/skills/do-alpha/files/SKILL.md")
        assert resp.status_code == 200
        assert resp.json()["content"].startswith("---")

    def test_the_reader_gets_text_with_newlines(
        self, client: TestClient, playbook_root: Path
    ) -> None:
        """The SPA's reader edits what it gets: line endings arrive as newlines and an
        undecodable byte as a replacement character."""
        (playbook_root / "skills" / "do-alpha" / "notes.md").write_bytes(b"a\r\nb\rc\xff\n")
        resp = client.get("/api/skills/do-alpha/files/notes.md")
        assert resp.status_code == 200
        assert resp.json()["content"] == "a\nb\nc\ufffd\n"

    def test_path_traversal_is_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/skills/do-alpha/files/..%2F..%2FREF-Alpha.md")
        assert resp.status_code in (400, 404)

    @intent("INT-GATE-003")
    def test_a_write_cannot_escape_the_skill_folder(
        self, client: TestClient, playbook_root: Path
    ) -> None:
        """Creation makes the containment check the only guard on this path."""
        for rel_path in (
            "..%2F..%2Fevil.md",
            "..%2Fevil.md",
            "templates%2F..%2F..%2Fevil.md",
        ):
            resp = client.put(f"/api/skills/do-alpha/files/{rel_path}", json={"raw": "x"})
            assert resp.status_code in (400, 404), rel_path
        assert not (playbook_root / "evil.md").exists()
        assert not (playbook_root / "skills" / "evil.md").exists()

    @intent("INT-GATE-003")
    def test_a_rejected_creation_keeps_a_folder_it_did_not_create(
        self, failing_client: TestClient, playbook_root: Path
    ) -> None:
        existing = playbook_root / "skills" / "do-alpha" / "templates"
        existing.mkdir()

        resp = failing_client.put(
            "/api/skills/do-alpha/files/templates/page.html", json={"raw": "<p>one</p>"}
        )
        assert resp.status_code == 422
        assert existing.is_dir()

    @intent("INT-GATE-001")
    def test_file_edit_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        original = failing_client.get("/api/skills/do-alpha/files/SKILL.md").json()["content"]
        resp = failing_client.put(
            "/api/skills/do-alpha/files/SKILL.md", json={"raw": "broken"}
        )
        assert resp.status_code == 422
        after = failing_client.get("/api/skills/do-alpha/files/SKILL.md").json()["content"]
        assert after == original

    @intent("INT-GATE-003")
    def test_a_file_the_skill_does_not_carry_is_created(self, client: TestClient) -> None:
        rel_path = "templates/page.html"
        assert client.get(f"/api/skills/do-alpha/files/{rel_path}").status_code == 404

        resp = client.put(f"/api/skills/do-alpha/files/{rel_path}", json={"raw": "<p>one</p>"})
        assert resp.status_code == 200

        written = client.get(f"/api/skills/do-alpha/files/{rel_path}")
        assert written.status_code == 200
        assert written.json()["content"] == "<p>one</p>"
        assert rel_path in client.get("/api/skills/do-alpha").json()["files"]

    @intent("INT-GATE-003")
    def test_rejected_creation_leaves_the_skill_folder_as_it_was(
        self, failing_client: TestClient, playbook_root: Path
    ) -> None:
        before = sorted(failing_client.get("/api/skills/do-alpha").json()["files"])

        resp = failing_client.put(
            "/api/skills/do-alpha/files/templates/page.html", json={"raw": "<p>one</p>"}
        )
        assert resp.status_code == 422

        assert sorted(failing_client.get("/api/skills/do-alpha").json()["files"]) == before
        assert not (playbook_root / "skills" / "do-alpha" / "templates").exists()


class TestInstallSkill:
    def test_skill_starts_uninstalled(self, local_client: TestClient) -> None:
        skill = local_client.get("/api/skills/do-alpha").json()
        assert skill["installed"] is False

    def test_install_copies_and_reports_in_sync(self, local_client: TestClient) -> None:
        resp = local_client.post("/api/skills/do-alpha/install")
        assert resp.status_code == 200
        assert resp.json() == {"installed": True, "in_sync": True}
        assert local_client.get("/api/skills/do-alpha").json()["in_sync"] is True

    def test_master_edit_marks_out_of_sync(self, local_client: TestClient) -> None:
        local_client.post("/api/skills/do-alpha/install")
        raw = local_client.get("/api/skills/do-alpha").json()["raw"]
        local_client.put("/api/skills/do-alpha", json={"raw": f"{raw}{chr(10)}More.{chr(10)}"})
        skill = local_client.get("/api/skills/do-alpha").json()
        assert skill["installed"] is True
        assert skill["in_sync"] is False

    def test_managed_deployment_refuses_runtime_install(self, client: TestClient) -> None:
        """A pod has no skills runtime; agents install on their own machines."""
        resp = client.post("/api/skills/do-alpha/install")
        assert resp.status_code == 409
        assert resp.json()["error"] == "UnsupportedCapabilityError"
        assert "/mcp" in resp.json()["detail"]


class TestCreateSkill:
    _PAYLOAD = {"name": "do-beta", "description": "Does beta things.", "refs": ["REF-Beta"]}

    @intent("INT-DERIVE-001")
    def test_create_skill_survives_when_gates_pass(self, client: TestClient) -> None:
        resp = client.post("/api/skills", json=self._PAYLOAD)
        assert resp.status_code == 201
        assert client.get("/api/skills/do-beta").json()["description"] == "Does beta things."
        assert "`do-beta`" in client.get("/api/playbook").json()["raw"]

    def test_duplicate_skill_returns_409(self, client: TestClient) -> None:
        assert client.post("/api/skills", json=self._PAYLOAD).status_code == 201
        assert client.post("/api/skills", json=self._PAYLOAD).status_code == 409

    def test_unknown_ref_returns_400(self, client: TestClient) -> None:
        resp = client.post("/api/skills", json={**self._PAYLOAD, "refs": ["REF-Nope"]})
        assert resp.status_code in (400, 404)

    @intent("INT-GATE-001")
    def test_create_skill_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        playbook_before = failing_client.get("/api/playbook").json()["raw"]
        resp = failing_client.post("/api/skills", json=self._PAYLOAD)
        assert resp.status_code == 422
        assert failing_client.get("/api/skills/do-beta").status_code == 404
        assert failing_client.get("/api/playbook").json()["raw"] == playbook_before


class TestAgentDocument:
    def test_agent_roster_is_listed(self, client: TestClient) -> None:
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        [agent] = resp.json()
        assert agent["name"] == "alpha-agent"
        assert agent["title"] == "The alpha agent"
        assert agent["description"] == "Runs the alpha thing end to end; hand it alpha work."
        assert agent["summary"] == "Runs the alpha thing end to end; hand it alpha work."

    def test_agent_detail_is_parsed(self, client: TestClient) -> None:
        resp = client.get("/api/agents/alpha-agent")
        assert resp.status_code == 200
        agent = resp.json()
        assert agent["galaxy"] == "craft"
        assert agent["refs"] == ["REF-Alpha"]
        assert agent["skills"] == ["do-alpha"]
        assert agent["doors"] == []
        assert agent["posture"] == {"permission": "auto", "writes": True, "fresh_eyes": False}
        assert agent["appearance"] == {
            "hair": "short",
            "headwear": "cap",
            "eyes": "dot",
            "face": "plain",
        }
        assert agent["body"].startswith("# Agent: The alpha agent")

    def test_unknown_agent_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/agents/no-such-agent")
        assert resp.status_code == 404
        assert resp.json()["error"] == "EntityNotFoundError"

    @intent("INT-GATE-001")
    def test_agent_rewrite_survives_when_gates_pass(self, client: TestClient) -> None:
        original = client.get("/api/agents/alpha-agent").json()["raw"]
        rewritten = original.replace("end to end", "end to end, calmly")
        resp = client.put("/api/agents/alpha-agent", json={"raw": rewritten})
        assert resp.status_code == 200
        assert "calmly" in client.get("/api/agents/alpha-agent").json()["raw"]

    @intent("INT-GATE-001")
    def test_agent_rewrite_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        original = failing_client.get("/api/agents/alpha-agent").json()["raw"]
        resp = failing_client.put("/api/agents/alpha-agent", json={"raw": "1. step one"})
        assert resp.status_code == 422
        assert failing_client.get("/api/agents/alpha-agent").json()["raw"] == original


class TestCreateAgent:
    _PAYLOAD = {
        "name": "beta-agent",
        "title": "The beta agent",
        "description": "Does the beta work; hand it beta.",
        "refs": ["REF-Beta"],
        "skills": ["do-alpha"],
    }

    @intent("INT-DERIVE-001")
    def test_create_agent_survives_when_gates_pass(self, client: TestClient) -> None:
        resp = client.post("/api/agents", json=self._PAYLOAD)
        assert resp.status_code == 201
        agent = client.get("/api/agents/beta-agent").json()
        assert agent["title"] == "The beta agent"
        assert agent["refs"] == ["REF-Beta"]
        assert agent["skills"] == ["do-alpha"]
        assert "Agents that orbit this REF" in client.get("/api/refs/REF-Beta").json()["raw"]

    def test_scaffolder_owns_the_posture_defaults(self, client: TestClient) -> None:
        """A fresh-eyes agent scaffolds read-only (permission plan, no appearance):
        the default lives in bootstrap-agent, not in a studio copy of it."""
        resp = client.post("/api/agents", json={**self._PAYLOAD, "fresh_eyes": True})
        assert resp.status_code == 201
        agent = client.get("/api/agents/beta-agent").json()
        assert agent["posture"] == {"permission": "plan", "writes": False, "fresh_eyes": True}
        assert agent["appearance"] is None

    def test_duplicate_agent_returns_409(self, client: TestClient) -> None:
        assert client.post("/api/agents", json=self._PAYLOAD).status_code == 201
        assert client.post("/api/agents", json=self._PAYLOAD).status_code == 409

    def test_unknown_ref_is_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/agents", json={**self._PAYLOAD, "refs": ["REF-Nope"]})
        assert resp.status_code in (400, 404)

    def test_unknown_skill_returns_400(self, client: TestClient) -> None:
        resp = client.post("/api/agents", json={**self._PAYLOAD, "skills": ["no-such-skill"]})
        assert resp.status_code == 400
        assert resp.json()["error"] == "InvalidRefInputError"

    def test_bad_name_returns_400(self, client: TestClient) -> None:
        resp = client.post("/api/agents", json={**self._PAYLOAD, "name": "BetaAgent"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "InvalidRefInputError"

    @intent("INT-GATE-001")
    def test_create_agent_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        """The no-procedure gate biting on a studio-authored agent takes this
        path: the gates reject, the agent file goes, and every cited REF's
        back-link section is restored byte-identical."""
        ref_before = failing_client.get("/api/refs/REF-Beta").json()["raw"]
        resp = failing_client.post("/api/agents", json=self._PAYLOAD)
        assert resp.status_code == 422
        assert failing_client.get("/api/agents/beta-agent").status_code == 404
        assert failing_client.get("/api/refs/REF-Beta").json()["raw"] == ref_before


class TestUpdatePlaybook:
    @intent("INT-GATE-001")
    def test_playbook_rewrite_survives_when_gates_pass(self, client: TestClient) -> None:
        original = client.get("/api/playbook").json()["raw"]
        resp = client.put("/api/playbook", json={"raw": original + "\n## Extra\n\nMore.\n"})
        assert resp.status_code == 200
        titles = [s["title"] for s in client.get("/api/playbook").json()["sections"]]
        assert "Extra" in titles

    @intent("INT-GATE-001")
    def test_playbook_rewrite_rolls_back_when_gates_fail(self, failing_client: TestClient) -> None:
        original = failing_client.get("/api/playbook").json()["raw"]
        resp = failing_client.put("/api/playbook", json={"raw": "# Broken\n"})
        assert resp.status_code == 422
        assert failing_client.get("/api/playbook").json()["raw"] == original


class TestValidation:
    def test_validate_returns_report(self, client: TestClient) -> None:
        resp = client.post("/api/validate")
        assert resp.status_code == 200
        report = resp.json()
        assert report["ok"] is True
        assert report["tests_passed"] is True
