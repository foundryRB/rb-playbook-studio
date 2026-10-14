"""Composition root: wires adapters and use cases."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypeVar

from studio.adapters.outbound.agent_renderer_script.script_agent_renderer import (
    ScriptAgentRenderer,
)
from studio.adapters.outbound.events import resolve_event_publisher
from studio.adapters.outbound.git_cli.cli_git_sync import CliGitSync
from studio.adapters.outbound.git_noop.noop_git_sync import NoopGitSync
from studio.adapters.outbound.playbook_fs.fs_playbook_repository import FsPlaybookRepository
from studio.adapters.outbound.playbook_fs.subprocess_playbook_validator import (
    SubprocessPlaybookValidator,
)
from studio.adapters.outbound.skill_runtime_fs.fs_skill_runtime import FsSkillRuntime
from studio.application.corpus_guard import CorpusGuard
from studio.application.ports.inbound.create_agent_port import CreateAgentPort
from studio.application.ports.inbound.create_door_port import CreateDoorPort
from studio.application.ports.inbound.create_ref_port import CreateRefPort
from studio.application.ports.inbound.create_skill_port import CreateSkillPort
from studio.application.ports.inbound.get_agent_files_port import GetAgentFilesPort
from studio.application.ports.inbound.get_agent_port import GetAgentPort
from studio.application.ports.inbound.get_door_port import GetDoorPort
from studio.application.ports.inbound.get_galaxy_port import GetGalaxyPort
from studio.application.ports.inbound.get_graph_port import GetGraphPort
from studio.application.ports.inbound.get_install_bundle_port import GetInstallBundlePort
from studio.application.ports.inbound.get_nebula_port import GetNebulaPort
from studio.application.ports.inbound.get_owners_port import GetOwnersPort
from studio.application.ports.inbound.get_playbook_port import GetPlaybookPort
from studio.application.ports.inbound.get_ref_port import GetRefPort
from studio.application.ports.inbound.get_skill_file_port import GetSkillFilePort
from studio.application.ports.inbound.get_skill_port import GetSkillPort
from studio.application.ports.inbound.get_skill_status_port import GetSkillStatusPort
from studio.application.ports.inbound.get_standing_port import GetStandingPort
from studio.application.ports.inbound.get_sync_status_port import GetSyncStatusPort
from studio.application.ports.inbound.install_skill_port import InstallSkillPort
from studio.application.ports.inbound.list_agent_runtimes_port import ListAgentRuntimesPort
from studio.application.ports.inbound.list_agents_port import ListAgentsPort
from studio.application.ports.inbound.list_claims_port import ListClaimsPort
from studio.application.ports.inbound.list_nebulae_port import ListNebulaePort
from studio.application.ports.inbound.push_changes_port import PushChangesPort
from studio.application.ports.inbound.refresh_content_port import RefreshContentPort
from studio.application.ports.inbound.run_validation_port import RunValidationPort
from studio.application.ports.inbound.update_agent_document_port import UpdateAgentDocumentPort
from studio.application.ports.inbound.update_door_document_port import UpdateDoorDocumentPort
from studio.application.ports.inbound.update_galaxy_document_port import (
    UpdateGalaxyDocumentPort,
)
from studio.application.ports.inbound.update_owners_port import UpdateOwnersPort
from studio.application.ports.inbound.update_playbook_document_port import (
    UpdatePlaybookDocumentPort,
)
from studio.application.ports.inbound.update_ref_document_port import UpdateRefDocumentPort
from studio.application.ports.inbound.update_ref_section_port import UpdateRefSectionPort
from studio.application.ports.inbound.update_skill_document_port import UpdateSkillDocumentPort
from studio.application.ports.inbound.update_skill_file_port import UpdateSkillFilePort
from studio.application.ports.outbound.agent_renderer import AgentRenderer
from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.application.ports.outbound.git_sync import GitSync
from studio.application.ports.outbound.playbook_validator import PlaybookValidator
from studio.application.use_cases.create_agent import CreateAgent
from studio.application.use_cases.create_door import CreateDoor
from studio.application.use_cases.create_ref import CreateRef
from studio.application.use_cases.create_skill import CreateSkill
from studio.application.use_cases.get_agent import GetAgent
from studio.application.use_cases.get_agent_files import GetAgentFiles
from studio.application.use_cases.get_door import GetDoor
from studio.application.use_cases.get_galaxy import GetGalaxy
from studio.application.use_cases.get_graph import GetGraph
from studio.application.use_cases.get_install_bundle import GetInstallBundle
from studio.application.use_cases.get_nebula import GetNebula
from studio.application.use_cases.get_owners import GetOwners
from studio.application.use_cases.get_playbook import GetPlaybook
from studio.application.use_cases.get_ref import GetRef
from studio.application.use_cases.get_skill import GetSkill
from studio.application.use_cases.get_skill_file import GetSkillFile
from studio.application.use_cases.get_skill_status import GetSkillStatus
from studio.application.use_cases.get_standing import GetStanding
from studio.application.use_cases.get_sync_status import GetSyncStatus
from studio.application.use_cases.install_skill import InstallSkill
from studio.application.use_cases.list_agent_runtimes import ListAgentRuntimes
from studio.application.use_cases.list_agents import ListAgents
from studio.application.use_cases.list_claims import ListClaims
from studio.application.use_cases.list_nebulae import ListNebulae
from studio.application.use_cases.push_changes import PushChanges
from studio.application.use_cases.refresh_content import RefreshContent
from studio.application.use_cases.run_validation import RunValidation
from studio.application.use_cases.update_agent_document import UpdateAgentDocument
from studio.application.use_cases.update_door_document import UpdateDoorDocument
from studio.application.use_cases.update_galaxy_document import UpdateGalaxyDocument
from studio.application.use_cases.update_owners import UpdateOwners
from studio.application.use_cases.update_playbook_document import UpdatePlaybookDocument
from studio.application.use_cases.update_ref_document import UpdateRefDocument
from studio.application.use_cases.update_ref_section import UpdateRefSection
from studio.application.use_cases.update_skill_document import UpdateSkillDocument
from studio.application.use_cases.update_skill_file import UpdateSkillFile
from studio.domain.model.actor import Actor

__all__ = ["Container", "resolve_playbook_root", "resolve_service_actor"]

_T = TypeVar("_T")
_W = TypeVar("_W")

_PLAYBOOK_ROOT_ENV = "STUDIO_PLAYBOOK_ROOT"
_RUNTIME_SKILLS_ENV = "STUDIO_RUNTIME_SKILLS_DIR"
_CONTENT_REPO_URL_ENV = "STUDIO_CONTENT_REPO_URL"
_GIT_AUTHOR_NAME_ENV = "STUDIO_GIT_AUTHOR_NAME"
_GIT_AUTHOR_EMAIL_ENV = "STUDIO_GIT_AUTHOR_EMAIL"
_GATES_USER_ENV = "STUDIO_GATES_USER"


def resolve_runtime_skills_dir() -> Path:
    """Runtime install dir: $STUDIO_RUNTIME_SKILLS_DIR, else ~/.claude/skills."""
    env = os.environ.get(_RUNTIME_SKILLS_ENV)
    if env:
        return Path(env)
    return Path.home() / ".claude" / "skills"


def resolve_playbook_root() -> Path:
    """Playbook checkout: $STUDIO_PLAYBOOK_ROOT, else the sibling-clone default.

    This file lives at <workspace>/playbook-studio/studio-backend/studio/,
    and the playbook is the sibling checkout <workspace>/playbook.
    """
    env = os.environ.get(_PLAYBOOK_ROOT_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "playbook"


def resolve_service_actor() -> Actor:
    """The studio's own identity: the configured git author, acting as the service.

    The managed clone commits with this identity, so a commit the service
    causes (a write over the shared machine credential, the stand-alone Basic
    gate, a local run, the poll) names the same author the clone's config does.
    """
    return Actor(
        name=os.environ.get(_GIT_AUTHOR_NAME_ENV, "playbook-studio"),
        email=os.environ.get(_GIT_AUTHOR_EMAIL_ENV, "playbook-studio@localhost"),
        service=True,
    )


def _resolve_git_sync(root: Path) -> GitSync:
    """Managed clone when a content repo URL is configured, no-op otherwise.

    The presence of $STUDIO_CONTENT_REPO_URL is the deployment signal: the
    deployed studio owns its clone (pull, commit, push); the local run edits
    a working tree the operator commits themselves.
    """
    remote_url = os.environ.get(_CONTENT_REPO_URL_ENV)
    if not remote_url:
        return NoopGitSync()
    service = resolve_service_actor()
    git = CliGitSync(
        root,
        remote_url=remote_url,
        author_name=service.name,
        author_email=service.email,
    )
    git.ensure_ready()
    return git


def _check(instance: object, port: type[_T]) -> _T:
    if not isinstance(instance, port):
        raise TypeError(f"{type(instance).__name__} does not satisfy {port.__name__}")
    return instance


class Container:
    """Instantiates outbound adapters once and builds use cases on demand."""

    def __init__(
        self,
        playbook_root: Path | None = None,
        validator: PlaybookValidator | None = None,
        runtime_skills_dir: Path | None = None,
        git_sync: GitSync | None = None,
        events: EventPublisher | None = None,
        agent_renderer: AgentRenderer | None = None,
    ) -> None:
        root = playbook_root or resolve_playbook_root()
        self._git = git_sync or _resolve_git_sync(root)
        # The event bus this studio's grant reached, or the logging publisher when
        # there is none; either way every act completes unchanged (REF-Events).
        self._events: EventPublisher = events or resolve_event_publisher()
        self._repository = FsPlaybookRepository(root)
        # The rights every write asks, and the one lock over the working tree.
        self._guard = CorpusGuard(self._repository)
        self.service = resolve_service_actor()
        # The gates run the corpus's own code; the deployed image names the
        # unprivileged user they run as ($STUDIO_GATES_USER).
        self._validator = validator or SubprocessPlaybookValidator(
            root, run_as=os.environ.get(_GATES_USER_ENV) or None
        )
        runtime_dir = runtime_skills_dir or resolve_runtime_skills_dir()
        self._skill_runtime = FsSkillRuntime(root, runtime_dir)
        # The installer owns every agent rendering; the studio serves them, never
        # spells them (playbook INT-TOOL-002).
        self._agent_renderer: AgentRenderer = agent_renderer or ScriptAgentRenderer(root)

    def _write(self, use_case: type[_W]) -> _W:
        """A gated write use case over this composition's adapters."""
        return use_case(self._repository, self._validator, self._git, self._guard, self._events)

    @property
    def sync_enabled(self) -> bool:
        """Whether this composition manages the clone (push/pull/status surface)."""
        return not isinstance(self._git, NoopGitSync)

    def rights(self) -> CorpusGuard:
        """The rights of the corpus as it stands, for surfaces rendering `can_edit`."""
        return self._guard

    @property
    def runtime_install_enabled(self) -> bool:
        """Whether a skills runtime exists on this machine.

        Only the operator-owned local run has one; a managed-clone deployment
        serves skills to agents, which install them on their own machines
        (the client-executes idiom, ADR-004).
        """
        return not self.sync_enabled

    def get_graph(self) -> GetGraphPort:
        return _check(GetGraph(self._repository), GetGraphPort)

    def get_playbook(self) -> GetPlaybookPort:
        return _check(GetPlaybook(self._repository), GetPlaybookPort)

    def get_galaxy(self) -> GetGalaxyPort:
        return _check(GetGalaxy(self._repository), GetGalaxyPort)

    def get_door(self) -> GetDoorPort:
        return _check(GetDoor(self._repository), GetDoorPort)

    def list_nebulae(self) -> ListNebulaePort:
        """The unearned zone, for the HTTP surface only (the quarantine)."""
        return _check(ListNebulae(self._repository), ListNebulaePort)

    def get_nebula(self) -> GetNebulaPort:
        """One nebula's stardust, for the HTTP surface only (the quarantine)."""
        return _check(GetNebula(self._repository), GetNebulaPort)

    def get_ref(self) -> GetRefPort:
        return _check(GetRef(self._repository), GetRefPort)

    def update_ref_section(self) -> UpdateRefSectionPort:
        return _check(
            self._write(UpdateRefSection),
            UpdateRefSectionPort,
        )

    def update_ref_document(self) -> UpdateRefDocumentPort:
        return _check(
            self._write(UpdateRefDocument),
            UpdateRefDocumentPort,
        )

    def create_ref(self) -> CreateRefPort:
        return _check(self._write(CreateRef), CreateRefPort)

    def create_skill(self) -> CreateSkillPort:
        return _check(self._write(CreateSkill), CreateSkillPort)

    def get_skill(self) -> GetSkillPort:
        return _check(GetSkill(self._repository), GetSkillPort)

    def update_skill_document(self) -> UpdateSkillDocumentPort:
        return _check(
            self._write(UpdateSkillDocument),
            UpdateSkillDocumentPort,
        )

    def list_agents(self) -> ListAgentsPort:
        return _check(ListAgents(self._repository), ListAgentsPort)

    def get_agent_files(self) -> GetAgentFilesPort:
        return _check(GetAgentFiles(self._repository, self._agent_renderer), GetAgentFilesPort)

    def get_install_bundle(self) -> GetInstallBundlePort:
        """Every skill and agent for one harness, applied client-side in one step."""
        return _check(
            GetInstallBundle(self._repository, self._agent_renderer, self._guard),
            GetInstallBundlePort,
        )

    def list_agent_runtimes(self) -> ListAgentRuntimesPort:
        """The harnesses the playbook renders agents for, from its installer."""
        return _check(ListAgentRuntimes(self._agent_renderer), ListAgentRuntimesPort)

    def get_agent(self) -> GetAgentPort:
        return _check(GetAgent(self._repository), GetAgentPort)

    def create_agent(self) -> CreateAgentPort:
        return _check(self._write(CreateAgent), CreateAgentPort)

    def update_agent_document(self) -> UpdateAgentDocumentPort:
        return _check(
            self._write(UpdateAgentDocument),
            UpdateAgentDocumentPort,
        )

    def get_skill_status(self) -> GetSkillStatusPort:
        return _check(GetSkillStatus(self._skill_runtime), GetSkillStatusPort)

    def install_skill(self) -> InstallSkillPort:
        return _check(InstallSkill(self._skill_runtime), InstallSkillPort)

    def get_skill_file(self) -> GetSkillFilePort:
        return _check(GetSkillFile(self._repository), GetSkillFilePort)

    def update_skill_file(self) -> UpdateSkillFilePort:
        return _check(
            self._write(UpdateSkillFile),
            UpdateSkillFilePort,
        )

    def update_galaxy_document(self) -> UpdateGalaxyDocumentPort:
        return _check(
            self._write(UpdateGalaxyDocument),
            UpdateGalaxyDocumentPort,
        )

    def update_playbook_document(self) -> UpdatePlaybookDocumentPort:
        return _check(
            self._write(UpdatePlaybookDocument),
            UpdatePlaybookDocumentPort,
        )

    def list_claims(self) -> ListClaimsPort:
        return _check(ListClaims(self._repository), ListClaimsPort)

    def run_validation(self) -> RunValidationPort:
        return _check(RunValidation(self._validator, self._guard), RunValidationPort)

    def get_sync_status(self) -> GetSyncStatusPort:
        return _check(GetSyncStatus(self._git), GetSyncStatusPort)

    def push_changes(self) -> PushChangesPort:
        return _check(PushChanges(self._git, self._guard, self._events), PushChangesPort)

    def refresh_content(self) -> RefreshContentPort:
        return _check(RefreshContent(self._git, self._guard), RefreshContentPort)

    def update_door_document(self) -> UpdateDoorDocumentPort:
        return _check(
            self._write(UpdateDoorDocument),
            UpdateDoorDocumentPort,
        )

    def create_door(self) -> CreateDoorPort:
        return _check(
            self._write(CreateDoor),
            CreateDoorPort,
        )

    def get_owners(self) -> GetOwnersPort:
        return _check(GetOwners(self._repository), GetOwnersPort)

    def update_owners(self) -> UpdateOwnersPort:
        return _check(
            self._write(UpdateOwners),
            UpdateOwnersPort,
        )

    def get_standing(self) -> GetStandingPort:
        return _check(GetStanding(self._repository, self._guard), GetStandingPort)
