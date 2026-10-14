"""Use case: gather the whole installable toolchain for one harness."""

from __future__ import annotations

from studio.application.corpus_guard import CorpusGuard
from studio.application.ports.outbound.agent_renderer import AgentRenderer, AgentRuntimeInfo
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.model.bundle_file import BundleFile
from studio.domain.model.install_bundle import AGENTS_PREFIX, SKILLS_PREFIX, InstallBundle
from studio.logging import get_logger

__all__ = ["GetInstallBundle"]

logger = get_logger(__name__)


class GetInstallBundle:
    """Returns every skill and every agent for one harness. Implements GetInstallBundlePort.

    The client-executes idiom at the scale of the toolchain: the same files the
    per-skill path serves, gathered into one artifact a script applies, so a full
    sync costs one download instead of a tool call per skill and agent. A skill
    file is its folder's bytes and executable bit, over the file list
    get_skill_files serves; an agent is rendered by the renderer get_agent_files
    uses, under the same file name; and the playbook installer travels with them,
    because the client applies the bundle with its rules. It reads under the
    corpus lock, so no write is halfway through the files it gathers.
    """

    def __init__(
        self, repository: PlaybookRepository, renderer: AgentRenderer, guard: CorpusGuard
    ) -> None:
        self._repository = repository
        self._renderer = renderer
        self._guard = guard

    def execute(self, *, runtime: str) -> InstallBundle:
        """Gather the bundle for a named harness, or raise EntityNotFoundError."""
        with self._guard.held():
            target = next((r for r in self._renderer.runtimes() if r.name == runtime), None)
            if target is None:
                raise EntityNotFoundError("runtime", runtime)
            return self._gather(target)

    def _gather(self, runtime: AgentRuntimeInfo) -> InstallBundle:
        files: list[BundleFile] = []
        for skill in self._repository.list_skills():
            files.extend(
                BundleFile(
                    path=f"{SKILLS_PREFIX}{skill.name}/{rel_path}",
                    data=self._repository.read_skill_file_bytes(name=skill.name, rel_path=rel_path),
                    executable=self._repository.skill_file_is_executable(
                        name=skill.name, rel_path=rel_path
                    ),
                )
                for rel_path in skill.files
            )
        files.extend(
            BundleFile(
                path=f"{AGENTS_PREFIX}{agent.name}{runtime.suffix}",
                data=self._renderer.render(raw=agent.raw, runtime=runtime.name).encode("utf-8"),
            )
            for agent in self._repository.list_agents()
        )
        logger.debug("Gathered an install bundle of %d file(s) for %s", len(files), runtime.name)
        return InstallBundle(
            runtime=runtime.name,
            files=tuple(files),
            installer=self._renderer.installer_source(),
        )
