"""Filesystem-backed PlaybookRepository."""

from __future__ import annotations

import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import yaml

from studio.adapters.outbound.playbook_fs.subprocess_playbook_validator import corpus_code_env
from studio.domain.exceptions.already_exists_error import AlreadyExistsError
from studio.domain.exceptions.app_error import AppError
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.exceptions.invalid_ref_input_error import InvalidRefInputError
from studio.domain.model.agent_doc import AgentAppearance, AgentDoc, AgentPosture
from studio.domain.model.door_doc import DoorDoc
from studio.domain.model.edge_kind import EdgeKind
from studio.domain.model.galaxy_doc import GalaxyDoc
from studio.domain.model.intent_claim import IntentClaim
from studio.domain.model.nebula_doc import NebulaDoc
from studio.domain.model.nebula_note import NebulaNote
from studio.domain.model.nebula_summary import NebulaSummary
from studio.domain.model.node_kind import NodeKind
from studio.domain.model.playbook_doc import PlaybookDoc
from studio.domain.model.playbook_section import PlaybookSection
from studio.domain.model.ref_doc import RefDoc
from studio.domain.model.ref_domain import RefDomain
from studio.domain.model.ref_section import RefSection
from studio.domain.model.reference_edge import ReferenceEdge
from studio.domain.model.rights import OWNERS_FILE
from studio.domain.model.skill_doc import SkillDoc
from studio.logging import get_logger

__all__ = ["FsPlaybookRepository"]

logger = get_logger(__name__)

_PLAYBOOK_NODE_ID = "AI-PLAYBOOK"
# The tail sections scripts/sync_backlinks.py owns, one per carried planet kind.
_GENERATED_SECTION_TITLES = (
    "Skills that instantiate this REF",
    "Agents that orbit this REF",
)

_SECTION_RE = re.compile(r"^## (\d+)\. (.+?)\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)")
_TITLE_RE = re.compile(r"^# REF: (.+?)\s*$")
_BARE_REF_RE = re.compile(r"`(REF-[A-Z][A-Za-z0-9-]*)(?:\.md)?`")
_NEBULA_SUBJECT_RE = re.compile(r"\*\*Subject\*\*:\s*(.+?)(?:\s*\*\*|$)")
_TERRITORY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _split_frontmatter_span(text: str) -> tuple[str, str] | None:
    """(frontmatter text, body) when a closed frontmatter block fronts the text."""
    if not text.startswith("---"):
        return None
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1:])
    return None


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """(frontmatter mapping, body) - frontmatter empty if absent."""
    span = _split_frontmatter_span(text)
    if span is None:
        return {}, text
    fm = yaml.safe_load(span[0]) or {}
    return fm, span[1]


def _split_frontmatter_lenient(text: str) -> tuple[dict, str]:
    """Like _split_frontmatter, but broken YAML or a non-mapping block degrades
    to empty frontmatter with the body kept. Nebula notes are foreign research
    material: one malformed note must never take a roster or a detail down."""
    span = _split_frontmatter_span(text)
    if span is None:
        return {}, text
    try:
        fm = yaml.safe_load(span[0]) or {}
    except yaml.YAMLError:
        return {}, span[1]
    return (fm, span[1]) if isinstance(fm, dict) else ({}, span[1])


def _strip_fences(text: str) -> str:
    """Blank out fenced code blocks so scans don't match example content."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


class FsPlaybookRepository:
    """Parses REFs, skills, claims, and edges from a playbook checkout."""

    def __init__(self, playbook_root: Path) -> None:
        self._root = playbook_root

    # -- discovery ----------------------------------------------------------
    # The corpus is one universe: documents live at the root and one level
    # into galaxies/<name>/. Identity is the name; the folder is shelving.

    def _rel(self, path: Path) -> str:
        """A corpus path as the rights see it: relative to the root, POSIX."""
        return path.relative_to(self._root).as_posix()

    def _galaxy_of(self, path: Path) -> str | None:
        parts = path.relative_to(self._root).parts
        if len(parts) >= 2 and parts[0] == "galaxies":
            return parts[1]
        return None

    def _ref_paths(self) -> list[Path]:
        paths = list(self._root.glob("REF-*.md")) + list(
            self._root.glob("galaxies/*/REF-*.md")
        )
        return sorted(paths, key=lambda p: p.stem)

    def _find_ref_path(self, name: str) -> Path | None:
        if not name.startswith("REF-"):
            return None
        direct = self._root / f"{name}.md"
        if direct.is_file():
            return direct
        return next(iter(sorted(self._root.glob(f"galaxies/*/{name}.md"))), None)

    def _skill_md_paths(self) -> list[Path]:
        paths = list((self._root / "skills").glob("*/SKILL.md")) + list(
            self._root.glob("galaxies/*/skills/*/SKILL.md")
        )
        return sorted(paths, key=lambda p: p.parent.name)

    def _find_skill_dir(self, name: str) -> Path | None:
        direct = self._root / "skills" / name
        if (direct / "SKILL.md").is_file():
            return direct
        candidates = sorted(self._root.glob(f"galaxies/*/skills/{name}"))
        return next((c for c in candidates if (c / "SKILL.md").is_file()), None)

    def _agent_paths(self) -> list[Path]:
        return sorted(self._root.glob("galaxies/*/agents/*.md"), key=lambda p: p.stem)

    def _find_agent_path(self, name: str) -> Path | None:
        return next(iter(sorted(self._root.glob(f"galaxies/*/agents/{name}.md"))), None)

    def _door_paths(self) -> list[tuple[Path, NodeKind]]:
        return [(p, NodeKind.MCP) for p in sorted(self._root.glob("galaxies/*/mcps/*.md"))] + [
            (p, NodeKind.RAG) for p in sorted(self._root.glob("galaxies/*/rags/*.md"))
        ]

    def _find_door_path(self, name: str) -> Path | None:
        for path, kind in self._door_paths():
            if self._parse_door(path, kind).name == name:
                return path
        return None

    def _hub_doc_paths(self) -> list[Path]:
        paths = [self._root / "AI-PLAYBOOK.md"] + sorted(
            self._root.glob("galaxies/*/GALAXY.md")
        )
        return [p for p in paths if p.is_file()]

    # -- reads --------------------------------------------------------------

    @staticmethod
    def _parse_titled_sections(
        lines: list[str], default_title: str
    ) -> tuple[str, list[PlaybookSection]]:
        title = default_title
        sections: list[PlaybookSection] = []
        in_fence = False
        current: str | None = None
        buffer: list[str] = []
        for line in lines:
            if _FENCE_RE.match(line):
                in_fence = not in_fence
            if not in_fence and line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip()
                continue
            if not in_fence and line.startswith("## "):
                if current is not None:
                    body = "\n".join(buffer).strip("\n")
                    sections.append(PlaybookSection(title=current, body=body))
                current = line[3:].strip()
                buffer = []
            elif current is not None:
                buffer.append(line)
        if current is not None:
            sections.append(PlaybookSection(title=current, body="\n".join(buffer).strip("\n")))
        return title, sections

    def get_playbook(self) -> PlaybookDoc:
        path = self._root / "AI-PLAYBOOK.md"
        if not path.is_file():
            raise EntityNotFoundError("playbook", "AI-PLAYBOOK.md")
        lines = path.read_text(encoding="utf-8").splitlines()
        title, sections = self._parse_titled_sections(lines, "AI Playbook")
        return PlaybookDoc(title=title, sections=tuple(sections), raw="\n".join(lines) + "\n")

    def get_galaxy(self, *, name: str) -> GalaxyDoc:
        path = self._root / "galaxies" / name / "GALAXY.md"
        if not path.is_file():
            raise EntityNotFoundError("galaxy", name)
        lines = path.read_text(encoding="utf-8").splitlines()
        title, sections = self._parse_titled_sections(lines, f"Galaxy: {name}")
        return GalaxyDoc(
            name=name,
            title=title,
            sections=tuple(sections),
            raw="\n".join(lines) + "\n",
            path=self._rel(path),
        )

    def write_galaxy_document(self, *, name: str, raw: str) -> GalaxyDoc:
        path = self._root / "galaxies" / name / "GALAXY.md"
        if not path.is_file():
            raise EntityNotFoundError("galaxy", name)
        path.write_text(raw, encoding="utf-8")
        logger.info("Wrote GALAXY.md for %s", name)
        return self.get_galaxy(name=name)

    def list_doors(self) -> list[DoorDoc]:
        doors = [self._parse_door(p, kind) for p, kind in self._door_paths()]
        return sorted(doors, key=lambda d: d.name)

    def get_door(self, *, name: str) -> DoorDoc:
        path = self._find_door_path(name)
        if path is None:
            raise EntityNotFoundError("door", name)
        kind = NodeKind.MCP if path.parent.name == "mcps" else NodeKind.RAG
        return self._parse_door(path, kind)

    def list_galaxies(self) -> list[str]:
        return sorted(p.parent.name for p in self._root.glob("galaxies/*/GALAXY.md"))

    def planned_path(self, *, kind: NodeKind, galaxy: str, name: str) -> str:
        """Where a new planet of `kind` named `name` lands in `galaxy`."""
        shelf = {
            NodeKind.REF: f"{name}.md",
            NodeKind.SKILL: f"skills/{name}",
            NodeKind.AGENT: f"agents/{name}.md",
            NodeKind.MCP: f"mcps/{name}.md",
            NodeKind.RAG: f"rags/{name}.md",
        }[kind]
        return f"galaxies/{galaxy}/{shelf}"

    def path_exists(self, *, path: str) -> bool:
        root = self._root.resolve()
        target = (root / path).resolve()
        return (target == root or root in target.parents) and target.exists()

    def read_owners(self) -> str | None:
        path = self._root / OWNERS_FILE
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def write_owners(self, *, text: str | None) -> None:
        path = self._root / OWNERS_FILE
        if text is None:
            path.unlink(missing_ok=True)
            logger.info("Removed OWNERS")
            return
        path.write_text(text, encoding="utf-8", newline="\n")
        logger.info("Wrote OWNERS (%d chars)", len(text))

    @staticmethod
    def _check_card_name(raw: str, name: str) -> None:
        """A card keeps the name it is filed under: the corpus finds it by that name."""
        try:
            fm, _ = _split_frontmatter(raw)
        except yaml.YAMLError as exc:
            raise InvalidRefInputError(f"the card's frontmatter is not YAML: {exc}") from exc
        stated = fm.get("name") if isinstance(fm, dict) else None
        if stated is not None and str(stated) != name:
            raise InvalidRefInputError(f"the card's frontmatter name must be {name!r}")

    def write_door_document(self, *, name: str, raw: str) -> DoorDoc:
        path = self._find_door_path(name)
        if path is None:
            raise EntityNotFoundError("door", name)
        if path.stem != name:
            raise InvalidRefInputError(f"card {name!r} is filed as {path.name}")
        self._check_card_name(raw, name)
        path.write_text(raw.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        logger.info("Wrote door card %s (%d chars)", name, len(raw))
        return self.get_door(name=name)

    def create_door_document(
        self, *, kind: NodeKind, galaxy: str, name: str, raw: str
    ) -> DoorDoc:
        if not (self._root / "galaxies" / galaxy / "GALAXY.md").is_file():
            raise EntityNotFoundError("galaxy", galaxy)
        path = self._root / self.planned_path(kind=kind, galaxy=galaxy, name=name)
        if self._find_door_path(name) is not None or path.exists():
            raise AlreadyExistsError("door", name)
        self._check_card_name(raw, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        logger.info("Created %s card %s in %s", kind, name, galaxy)
        return self._parse_door(path, kind)

    def delete_door_document(self, *, name: str) -> None:
        path = self._find_door_path(name)
        if path is not None:
            path.unlink()
            logger.info("Deleted door card %s", name)

    def _parse_door(self, path: Path, kind: NodeKind) -> DoorDoc:
        raw = path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(raw)
        summary = next(
            (ln.lstrip("> ").strip() for ln in body.splitlines() if ln.startswith(">")), ""
        )
        return DoorDoc(
            name=str(fm.get("name") or path.stem),
            kind=kind,
            galaxy=self._galaxy_of(path) or "",
            refs=tuple(str(r) for r in (fm.get("refs") or [])),
            summary=summary,
            raw=raw,
            path=self._rel(path),
        )

    def list_refs(self) -> list[RefDoc]:
        return [self._parse_ref(p) for p in self._ref_paths()]

    def get_ref(self, *, name: str) -> RefDoc:
        path = self._find_ref_path(name)
        if path is None:
            raise EntityNotFoundError("REF", name)
        return self._parse_ref(path)

    def list_skills(self) -> list[SkillDoc]:
        return [self._parse_skill(p) for p in self._skill_md_paths()]

    def get_skill(self, *, name: str) -> SkillDoc:
        skill_dir = self._find_skill_dir(name)
        if skill_dir is None:
            raise EntityNotFoundError("skill", name)
        return self._parse_skill(skill_dir / "SKILL.md")

    def list_agents(self) -> list[AgentDoc]:
        return [self._parse_agent(p) for p in self._agent_paths()]

    def get_agent(self, *, name: str) -> AgentDoc:
        path = self._find_agent_path(name)
        if path is None:
            raise EntityNotFoundError("agent", name)
        return self._parse_agent(path)

    def list_claims(self) -> list[IntentClaim]:
        intent_path = self._root / "intent.yaml"
        if not intent_path.is_file():
            return []
        spec = yaml.safe_load(intent_path.read_text(encoding="utf-8")) or {}
        return [
            IntentClaim(
                claim_id=claim_id,
                statement=str(claim.get("statement", "")),
                rationale=str(claim.get("rationale", "")),
                criticality=str(claim.get("criticality", "")),
                status=str(claim.get("status", "")),
            )
            for claim_id, claim in spec.items()
            if isinstance(claim, dict)
        ]

    def list_edges(self) -> list[ReferenceEdge]:
        """Edges in authored order: a planet's FIRST skill-to-ref, door-to-ref,
        or agent-to-ref edge is its declared HOME sun (REF-Universe §3), so
        frontmatter order must survive into the graph."""
        ref_names = {p.stem for p in self._ref_paths()}
        edges: list[ReferenceEdge] = []
        seen: set[ReferenceEdge] = set()

        def add(edge: ReferenceEdge) -> None:
            if edge not in seen:
                seen.add(edge)
                edges.append(edge)

        for hub_path in self._hub_doc_paths():
            hub_text = _strip_fences(hub_path.read_text(encoding="utf-8"))
            for target in _BARE_REF_RE.findall(hub_text):
                if target in ref_names:
                    add(ReferenceEdge(_PLAYBOOK_NODE_ID, target, EdgeKind.PLAYBOOK_TO_REF))

        for ref_path in self._ref_paths():
            body = _strip_fences(ref_path.read_text(encoding="utf-8"))
            for target in _BARE_REF_RE.findall(body):
                if target in ref_names and target != ref_path.stem:
                    add(ReferenceEdge(ref_path.stem, target, EdgeKind.REF_TO_REF))

        skills = self.list_skills()
        for skill in skills:
            for target in skill.refs:
                if target in ref_names:
                    add(ReferenceEdge(skill.name, target, EdgeKind.SKILL_TO_REF))

        doors = self.list_doors()
        for door in doors:
            for target in door.refs:
                if target in ref_names:
                    add(ReferenceEdge(door.name, target, EdgeKind.DOOR_TO_REF))

        skill_names = {s.name for s in skills}
        door_names = {d.name for d in doors}
        for agent in self.list_agents():
            for target in agent.refs:
                if target in ref_names:
                    add(ReferenceEdge(agent.name, target, EdgeKind.AGENT_TO_REF))
            for target in agent.skills:
                if target in skill_names:
                    add(ReferenceEdge(agent.name, target, EdgeKind.AGENT_TO_SKILL))
            for target in agent.doors:
                if target in door_names:
                    add(ReferenceEdge(agent.name, target, EdgeKind.AGENT_TO_DOOR))

        return edges

    # -- nebulae ------------------------------------------------------------
    # The unearned zone (REF-Universe: nebulae/<territory>/) is parsed for the
    # human surfaces only. Nothing here feeds the discovery globs above, the
    # graph, or the MCP door: the quarantine is structural, not filtered.

    def _nebula_dirs(self) -> list[Path]:
        return sorted(
            (p.parent for p in self._root.glob("nebulae/*/NEBULA.md")),
            key=lambda p: p.name,
        )

    def _nebula_note_paths(self, nebula_dir: Path) -> list[Path]:
        return sorted(
            (p for p in nebula_dir.glob("*.md") if p.name != "NEBULA.md"),
            key=lambda p: p.stem,
        )

    @staticmethod
    def _nebula_subject(nebula_md: str) -> str:
        for line in nebula_md.splitlines():
            m = _NEBULA_SUBJECT_RE.search(line)
            if m:
                return m.group(1).strip().rstrip(".")
        return ""

    @staticmethod
    def _as_list(value: object) -> tuple[str, ...]:
        """A frontmatter list field, tolerating a scalar where a list belongs."""
        if value is None:
            return ()
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        return (str(value),)

    @classmethod
    def _parse_nebula_note(cls, path: Path) -> NebulaNote:
        raw = path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter_lenient(raw)
        vote = fm.get("vote")
        return NebulaNote(
            name=path.stem,
            note_type=str(fm.get("type", "")),
            confidence=str(fm.get("confidence", "")),
            vote=None if vote is None else str(vote),
            seats=cls._as_list(fm.get("seats")),
            sources=cls._as_list(fm.get("sources")),
            links=cls._as_list(fm.get("links")),
            status=str(fm.get("status", "")),
            body=body.strip("\n"),
        )

    def list_nebulae(self) -> list[NebulaSummary]:
        summaries: list[NebulaSummary] = []
        for nebula_dir in self._nebula_dirs():
            nebula_md = (nebula_dir / "NEBULA.md").read_text(encoding="utf-8")
            statuses = [
                self._parse_nebula_note(p).status for p in self._nebula_note_paths(nebula_dir)
            ]
            summaries.append(
                NebulaSummary(
                    territory=nebula_dir.name,
                    subject=self._nebula_subject(nebula_md),
                    note_count=len(statuses),
                    unsmelted=statuses.count("unsmelted"),
                    taken=statuses.count("taken"),
                    burned=statuses.count("burned"),
                )
            )
        return summaries

    def get_nebula(self, *, territory: str) -> NebulaDoc:
        # A territory is a strict slug; anything else (dots, slashes, and on
        # Windows backslashes) could escape nebulae/ once joined into a path.
        if not _TERRITORY_RE.match(territory):
            raise EntityNotFoundError("nebula", territory)
        nebula_dir = self._root / "nebulae" / territory
        nebula_md_path = nebula_dir / "NEBULA.md"
        if not nebula_md_path.is_file():
            raise EntityNotFoundError("nebula", territory)
        nebula_md = nebula_md_path.read_text(encoding="utf-8")
        notes = tuple(
            self._parse_nebula_note(p) for p in self._nebula_note_paths(nebula_dir)
        )
        return NebulaDoc(
            territory=territory,
            subject=self._nebula_subject(nebula_md),
            raw=nebula_md,
            notes=notes,
        )

    # -- writes -------------------------------------------------------------

    def write_ref_document(self, *, ref_name: str, raw: str) -> RefDoc:
        path = self._find_ref_path(ref_name)
        if path is None:
            raise EntityNotFoundError("REF", ref_name)
        path.write_text(raw.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        logger.info("Wrote %s (full document, %d chars)", ref_name, len(raw))
        return self._parse_ref(path)

    def write_playbook_document(self, *, raw: str) -> PlaybookDoc:
        path = self._root / "AI-PLAYBOOK.md"
        path.write_text(raw.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        logger.info("Wrote AI-PLAYBOOK.md (%d chars)", len(raw))
        return self.get_playbook()

    def write_skill_document(self, *, name: str, raw: str) -> SkillDoc:
        skill_dir = self._find_skill_dir(name)
        if skill_dir is None:
            raise EntityNotFoundError("skill", name)
        path = skill_dir / "SKILL.md"
        path.write_text(raw.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        logger.info("Wrote skill %s (%d chars)", name, len(raw))
        return self._parse_skill(path)

    def scaffold_ref(
        self, *, name: str, domain: str, title: str, summary: str, galaxy: str = "craft"
    ) -> RefDoc:
        if self._find_ref_path(name) is not None:
            raise AlreadyExistsError("REF", name)
        self._run_bootstrap(
            "bootstrap-ref",
            [
                "--name",
                name,
                "--domain",
                domain,
                "--title",
                title,
                "--summary",
                summary,
                "--galaxy",
                galaxy,
            ],
        )
        path = self._find_ref_path(name)
        if path is None:
            raise AppError(f"bootstrap-ref reported success but {name}.md was not created")
        return self._parse_ref(path)

    def scaffold_skill(
        self, *, name: str, description: str, refs: list[str], galaxy: str = "craft"
    ) -> SkillDoc:
        if self._find_skill_dir(name) is not None:
            raise AlreadyExistsError("skill", name)
        self._run_bootstrap(
            "bootstrap-skill",
            [
                "--name",
                name,
                "--description",
                description,
                "--refs",
                ",".join(refs),
                "--galaxy",
                galaxy,
            ],
        )
        return self.get_skill(name=name)

    def delete_skill_document(self, *, name: str) -> None:
        skill_dir = self._find_skill_dir(name)
        if skill_dir is not None:
            shutil.rmtree(skill_dir)
            logger.info("Deleted skill %s", name)

    def write_agent_document(self, *, name: str, raw: str) -> AgentDoc:
        path = self._find_agent_path(name)
        if path is None:
            raise EntityNotFoundError("agent", name)
        path.write_text(raw.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        logger.info("Wrote agent %s (%d chars)", name, len(raw))
        return self._parse_agent(path)

    def scaffold_agent(
        self,
        *,
        name: str,
        title: str,
        description: str,
        refs: list[str],
        skills: list[str],
        doors: list[str],
        galaxy: str = "craft",
        permission: str | None = None,
        writes: bool = False,
        fresh_eyes: bool = False,
        hair: str | None = None,
        headwear: str | None = None,
        eyes: str | None = None,
        face: str | None = None,
    ) -> AgentDoc:
        if self._find_agent_path(name) is not None:
            raise AlreadyExistsError("agent", name)
        argv = [
            "--name",
            name,
            "--title",
            title,
            "--description",
            description,
            "--refs",
            ",".join(refs),
            "--skills",
            ",".join(skills),
            "--galaxy",
            galaxy,
        ]
        if doors:
            argv += ["--doors", ",".join(doors)]
        if permission:
            argv += ["--permission", permission]
        if writes:
            argv.append("--writes")
        if fresh_eyes:
            argv.append("--fresh-eyes")
        # Appearance flags ride only when given: bootstrap-agent owns the defaults.
        for flag, value in (
            ("--hair", hair),
            ("--headwear", headwear),
            ("--eyes", eyes),
            ("--face", face),
        ):
            if value:
                argv += [flag, value]
        self._run_bootstrap("bootstrap-agent", argv)
        return self.get_agent(name=name)

    def delete_agent_document(self, *, name: str) -> None:
        path = self._find_agent_path(name)
        if path is not None:
            path.unlink()
            logger.info("Deleted agent %s", name)

    def _find_scaffolder(self, name: str) -> Path | None:
        candidates = [self._root / "skills" / name / "bootstrap.py"] + sorted(
            self._root.glob(f"galaxies/*/skills/{name}/bootstrap.py")
        )
        return next((c for c in candidates if c.is_file()), None)

    def _run_bootstrap(self, scaffolder: str, argv: list[str]) -> None:
        """Invoke a playbook scaffolder skill; the playbook owns the template."""
        script = self._find_scaffolder(scaffolder)
        if script is None:
            raise EntityNotFoundError("scaffolder", scaffolder)
        proc = subprocess.run(
            [sys.executable, str(script), "--playbook-root", str(self._root), *argv],
            env=corpus_code_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if proc.returncode == 2:
            raise InvalidRefInputError(proc.stderr.strip() or "scaffolder rejected the input")
        if proc.returncode != 0:
            raise AppError(f"{scaffolder} failed: {proc.stderr.strip()[:500]}")

    def sync_backlinks(self) -> None:
        """Regenerate the back-link sections from the playbook's own script.

        The tail sections of a REF quote the frontmatter of every planet that
        cites it, and scripts/sync_backlinks.py is their author. A write path
        that changes frontmatter runs this so the sections state what the
        frontmatter says; the studio never composes those sections itself.

        A checkout without the script skips the regeneration, because the same
        absence takes the gates down with it: the playbook's own suite imports
        sync_backlinks from scripts/ at module level, so pytest fails collection
        and every write is refused with its state intact. Nothing stale lands
        through this branch. It does not mean the sections are absent -- they
        are plain text in the REFs and outlive the script -- only that reaching
        this state takes hand-deleting scripts/ from a managed clone (#14).
        """
        script = self._root / "scripts" / "sync_backlinks.py"
        if not script.is_file():
            logger.warning("No scripts/sync_backlinks.py in the checkout; skipping the sync")
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=self._root,
                env=corpus_code_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            # A stalled or unspawnable script leaves the caller mid-write, so it
            # answers as a refusal like a non-zero exit rather than escaping.
            raise AppError(f"sync_backlinks failed: {exc}") from exc
        if proc.returncode != 0:
            raise AppError(f"sync_backlinks failed: {proc.stderr.strip()[:500]}")
        logger.info("Regenerated back-link sections")

    def delete_ref_document(self, *, ref_name: str) -> None:
        path = self._find_ref_path(ref_name)
        if path is not None:
            path.unlink()
            logger.info("Deleted %s", ref_name)

    def write_ref_section(self, *, ref_name: str, number: int, body: str) -> RefDoc:
        path = self._find_ref_path(ref_name)
        if path is None:
            raise EntityNotFoundError("REF", ref_name)
        text = path.read_text(encoding="utf-8")
        span = self._section_span(text, number)
        if span is None:
            raise EntityNotFoundError("section", f"{ref_name} §{number}")
        start, end = span
        lines = text.splitlines()
        new_body = body.strip("\n").splitlines()
        new_lines = lines[: start + 1] + [""] + new_body + [""] + lines[end:]
        path.write_text("\n".join(new_lines).rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        logger.info("Wrote %s section %d (%d body lines)", ref_name, number, len(new_body))
        return self._parse_ref(path)

    # -- parsing ------------------------------------------------------------

    def _parse_skill(self, path: Path) -> SkillDoc:
        raw = path.read_text(encoding="utf-8")
        fm, _ = _split_frontmatter(raw)
        skill_dir = path.parent
        files = sorted(
            f.relative_to(skill_dir).as_posix()
            for f in skill_dir.rglob("*")
            if f.is_file() and "__pycache__" not in f.parts
        )
        files.sort(key=lambda f: (f != "SKILL.md", f))
        return SkillDoc(
            name=str(fm.get("name") or skill_dir.name),
            description=str(fm.get("description", "")),
            refs=tuple(str(r) for r in (fm.get("refs") or [])),
            raw=raw,
            files=tuple(files),
            galaxy=self._galaxy_of(path),
            path=self._rel(skill_dir),
        )

    def _parse_agent(self, path: Path) -> AgentDoc:
        raw = path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(raw)
        posture = fm.get("posture") if isinstance(fm.get("posture"), dict) else {}
        appearance_fm = fm.get("appearance")
        appearance = (
            AgentAppearance(
                hair=str(appearance_fm.get("hair", "")),
                headwear=str(appearance_fm.get("headwear", "")),
                eyes=str(appearance_fm.get("eyes", "")),
                face=str(appearance_fm.get("face", "")),
            )
            if isinstance(appearance_fm, dict)
            else None
        )
        description = str(fm.get("description") or "").strip()
        return AgentDoc(
            name=str(fm.get("name") or path.stem),
            title=str(fm.get("title") or path.stem),
            description=description,
            galaxy=self._galaxy_of(path) or "",
            refs=self._as_list(fm.get("refs")),
            skills=self._as_list(fm.get("skills")),
            doors=self._as_list(fm.get("doors")),
            posture=AgentPosture(
                permission=str(posture.get("permission", "")),
                writes=bool(posture.get("writes", False)),
                fresh_eyes=bool(posture.get("fresh_eyes", False)),
            ),
            appearance=appearance,
            summary=description,
            raw=raw,
            path=self._rel(path),
        )

    def _skill_file_path(self, name: str, rel_path: str) -> Path:
        found = self._find_skill_dir(name)
        if found is None:
            raise EntityNotFoundError("skill", name)
        skill_dir = found.resolve()
        candidate = (skill_dir / rel_path).resolve()
        if skill_dir not in candidate.parents and candidate != skill_dir:
            raise InvalidRefInputError(f"path escapes the skill folder: {rel_path!r}")
        return candidate

    def read_skill_file(self, *, name: str, rel_path: str) -> str:
        path = self._skill_file_path(name, rel_path)
        if not path.is_file():
            raise EntityNotFoundError("skill file", f"{name}/{rel_path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def read_skill_file_bytes(self, *, name: str, rel_path: str) -> bytes:
        path = self._skill_file_path(name, rel_path)
        if not path.is_file():
            raise EntityNotFoundError("skill file", f"{name}/{rel_path}")
        return path.read_bytes()

    def skill_file_is_executable(self, *, name: str, rel_path: str) -> bool:
        path = self._skill_file_path(name, rel_path)
        if not path.is_file():
            raise EntityNotFoundError("skill file", f"{name}/{rel_path}")
        return bool(path.stat().st_mode & stat.S_IXUSR)

    def skill_file_exists(self, *, name: str, rel_path: str) -> bool:
        return self._skill_file_path(name, rel_path).is_file()

    def write_skill_file(self, *, name: str, rel_path: str, content: str) -> list[str]:
        """Write the file, creating it and any folder it sits in.

        A skill carries whatever files it ships (templates, scripts, reference
        pages), so authoring one through this door means writing paths that do
        not exist yet. The gate above decides whether the write survives, so the
        folders this brought into being are named in the return value: they are
        what a rollback has to take away again, and nothing else.
        """
        path = self._skill_file_path(name, rel_path)
        if path.is_dir():
            raise InvalidRefInputError(f"path is a directory: {rel_path!r}")
        created: list[Path] = []
        missing = path.parent
        while not missing.exists():
            created.append(missing)
            missing = missing.parent
        # The first ancestor that does exist has to be a folder, or the mkdir
        # below walks down into a file and fails as an unhandled OS error.
        if not missing.is_dir():
            raise InvalidRefInputError(f"path is under a file: {rel_path!r}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        logger.info("Wrote skill file %s/%s (%d chars)", name, rel_path, len(content))
        skill_dir = self._skill_dir_or_raise(name)
        return [d.relative_to(skill_dir).as_posix() for d in created]

    def delete_skill_file(
        self, *, name: str, rel_path: str, created_dirs: list[str] | None = None
    ) -> None:
        """Remove the file, and the folders the write reports having created.

        Rolling back a creation restores the skill folder as it was, so a folder
        that was already there stays, empty or not.
        """
        path = self._skill_file_path(name, rel_path)
        if path.is_file():
            path.unlink()
        skill_dir = self._skill_dir_or_raise(name)
        for rel_dir in sorted(created_dirs or [], key=len, reverse=True):
            candidate = (skill_dir / rel_dir).resolve()
            if skill_dir not in candidate.parents:
                continue
            if candidate.is_dir() and not any(candidate.iterdir()):
                candidate.rmdir()
        logger.info("Deleted skill file %s/%s", name, rel_path)

    def _skill_dir_or_raise(self, name: str) -> Path:
        found = self._find_skill_dir(name)
        if found is None:
            raise EntityNotFoundError("skill", name)
        return found.resolve()

    def _parse_ref(self, path: Path) -> RefDoc:
        raw = path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(raw)
        domain = RefDomain(str(fm.get("domain", RefDomain.PRACTICE)))
        lines = body.splitlines()

        title = path.stem
        summary = ""
        for line in lines:
            if not line.strip():
                continue
            m = _TITLE_RE.match(line)
            if m and title == path.stem:
                title = m.group(1)
                continue
            if line.startswith(">") and not summary:
                summary = line.lstrip("> ").strip()
                break
            if title != path.stem:
                break

        sections: list[RefSection] = []
        in_fence = False
        current: tuple[int, str] | None = None
        buffer: list[str] = []
        for line in lines:
            if _FENCE_RE.match(line):
                in_fence = not in_fence
            m = None if in_fence else _SECTION_RE.match(line)
            if m:
                if current is not None:
                    sections.append(self._make_section(current, buffer))
                current = (int(m.group(1)), m.group(2))
                buffer = []
            elif current is not None:
                buffer.append(line)
        if current is not None:
            sections.append(self._make_section(current, buffer))

        return RefDoc(
            name=path.stem,
            domain=domain,
            title=title,
            summary=summary,
            sections=tuple(sections),
            raw=raw,
            galaxy=self._galaxy_of(path),
            path=self._rel(path),
        )

    @staticmethod
    def _make_section(header: tuple[int, str], buffer: list[str]) -> RefSection:
        number, section_title = header
        return RefSection(
            number=number,
            title=section_title,
            body="\n".join(buffer).strip("\n"),
            generated=section_title in _GENERATED_SECTION_TITLES,
        )

    @staticmethod
    def _section_span(text: str, number: int) -> tuple[int, int] | None:
        """(heading line index, exclusive end line index) of section `number`."""
        lines = text.splitlines()
        in_fence = False
        start: int | None = None
        for i, line in enumerate(lines):
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = _SECTION_RE.match(line)
            if start is None:
                if m and int(m.group(1)) == number:
                    start = i
            elif line.startswith("## "):
                return start, i
        if start is None:
            return None
        return start, len(lines)
