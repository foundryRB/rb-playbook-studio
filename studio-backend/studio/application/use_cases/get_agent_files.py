"""Use case: serve one agent rendered for the harnesses that read it."""

from __future__ import annotations

from studio.application.ports.outbound.agent_renderer import AgentRenderer
from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.model.rendered_agent import RenderedAgent
from studio.logging import get_logger

__all__ = ["GetAgentFiles"]

logger = get_logger(__name__)


class GetAgentFiles:
    """Returns one agent already rendered, ready to write. Implements GetAgentFilesPort.

    The client-executes idiom applied to the roster: the server owns the corpus
    and the rendering, the writes on the client's machine are the client's. A
    caller asking for no particular runtime gets every rendering, because a
    session that syncs the roster wants the harness it runs and cannot be relied
    on to know which name that is.
    """

    def __init__(self, repository: PlaybookRepository, renderer: AgentRenderer) -> None:
        self._repository = repository
        self._renderer = renderer

    def execute(self, *, name: str, runtime: str | None = None) -> tuple[RenderedAgent, ...]:
        """Render the named agent for one harness, or for all of them."""
        doc = self._repository.get_agent(name=name)
        wanted = [r for r in self._renderer.runtimes() if runtime in (None, r.name)]
        if runtime is not None and not wanted:
            # Name the runtime that does not exist rather than returning nothing.
            self._renderer.render(raw=doc.raw, runtime=runtime)
        logger.debug("Rendering agent %s for %d runtime(s)", name, len(wanted))
        return tuple(
            RenderedAgent(
                name=doc.name,
                runtime=target.name,
                filename=f"{doc.name}{target.suffix}",
                content=self._renderer.render(raw=doc.raw, runtime=target.name),
                install_dir_hint=target.install_hint,
            )
            for target in wanted
        )
