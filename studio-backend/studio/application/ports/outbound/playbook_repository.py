"""Outbound port: read and write the playbook checkout."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from studio.domain.model.agent_doc import AgentDoc
from studio.domain.model.door_doc import DoorDoc
from studio.domain.model.galaxy_doc import GalaxyDoc
from studio.domain.model.intent_claim import IntentClaim
from studio.domain.model.nebula_doc import NebulaDoc
from studio.domain.model.nebula_summary import NebulaSummary
from studio.domain.model.node_kind import NodeKind
from studio.domain.model.playbook_doc import PlaybookDoc
from studio.domain.model.ref_doc import RefDoc
from studio.domain.model.reference_edge import ReferenceEdge
from studio.domain.model.skill_doc import SkillDoc

__all__ = ["PlaybookRepository"]


@runtime_checkable
class PlaybookRepository(Protocol):
    """Parses the playbook folder into domain objects and applies edits.

    Scaffolding delegates to the playbook's own bootstrap-ref / bootstrap-skill
    / bootstrap-agent scripts, so the studio never owns a parallel copy of the
    templates.
    """

    def get_playbook(self) -> PlaybookDoc: ...

    def get_galaxy(self, *, name: str) -> GalaxyDoc: ...

    def write_galaxy_document(self, *, name: str, raw: str) -> GalaxyDoc: ...

    def list_doors(self) -> list[DoorDoc]: ...

    def get_door(self, *, name: str) -> DoorDoc: ...

    def write_door_document(self, *, name: str, raw: str) -> DoorDoc: ...

    def create_door_document(
        self, *, kind: NodeKind, galaxy: str, name: str, raw: str
    ) -> DoorDoc: ...

    def delete_door_document(self, *, name: str) -> None: ...

    def list_galaxies(self) -> list[str]: ...

    def planned_path(self, *, kind: NodeKind, galaxy: str, name: str) -> str:
        """The corpus path a new planet would land at, for the rights to judge."""
        ...

    def path_exists(self, *, path: str) -> bool: ...

    def read_owners(self) -> str | None:
        """The OWNERS text at the playbook root, or None when there is none."""
        ...

    def write_owners(self, *, text: str | None) -> None:
        """Write OWNERS, or remove it with None (a rollback to its absence)."""
        ...

    def write_playbook_document(self, *, raw: str) -> PlaybookDoc: ...

    def list_refs(self) -> list[RefDoc]: ...

    def get_ref(self, *, name: str) -> RefDoc: ...

    def list_skills(self) -> list[SkillDoc]: ...

    def get_skill(self, *, name: str) -> SkillDoc: ...

    def list_agents(self) -> list[AgentDoc]: ...

    def get_agent(self, *, name: str) -> AgentDoc: ...

    def list_claims(self) -> list[IntentClaim]: ...

    def list_edges(self) -> list[ReferenceEdge]: ...

    def list_nebulae(self) -> list[NebulaSummary]: ...

    def get_nebula(self, *, territory: str) -> NebulaDoc: ...

    def write_ref_section(self, *, ref_name: str, number: int, body: str) -> RefDoc: ...

    def write_ref_document(self, *, ref_name: str, raw: str) -> RefDoc: ...

    def write_skill_document(self, *, name: str, raw: str) -> SkillDoc: ...

    def write_agent_document(self, *, name: str, raw: str) -> AgentDoc: ...

    def read_skill_file(self, *, name: str, rel_path: str) -> str: ...

    def read_skill_file_bytes(self, *, name: str, rel_path: str) -> bytes: ...

    def skill_file_is_executable(self, *, name: str, rel_path: str) -> bool: ...

    def skill_file_exists(self, *, name: str, rel_path: str) -> bool: ...

    def write_skill_file(self, *, name: str, rel_path: str, content: str) -> list[str]: ...

    def delete_skill_file(
        self, *, name: str, rel_path: str, created_dirs: list[str] | None = None
    ) -> None: ...

    def sync_backlinks(self) -> None: ...

    def scaffold_ref(
        self, *, name: str, domain: str, title: str, summary: str, galaxy: str = "craft"
    ) -> RefDoc: ...

    def scaffold_skill(
        self, *, name: str, description: str, refs: list[str], galaxy: str = "craft"
    ) -> SkillDoc: ...

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
    ) -> AgentDoc: ...

    def delete_ref_document(self, *, ref_name: str) -> None: ...

    def delete_skill_document(self, *, name: str) -> None: ...

    def delete_agent_document(self, *, name: str) -> None: ...
