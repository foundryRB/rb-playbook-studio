"""AgentRenderer backed by the playbook's scripts/install_playbook.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from studio.domain.exceptions.app_error import AppError
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.logging import get_logger

__all__ = ["ScriptAgentRenderer"]

logger = get_logger(__name__)

_SCRIPT = ("scripts", "install_playbook.py")


class ScriptAgentRenderer:
    """Renders agents by calling the playbook installer's own render functions.

    The installer owns every agent rendering and publishes them as AGENT_RUNTIMES
    (which harnesses exist, how each spells an agent, where each reads them).
    Loading that module is how the studio serves a rendered agent without holding
    a second copy of the mapping: a client with no clone gets exactly the file the
    installer would have written, and the two can never drift because there is
    only one of them. Implements AgentRenderer.

    The playbook clone is pulled in place while the process runs, so the module is
    loaded again whenever the file's bytes change, and the installer bytes served are
    the ones the loaded module came from: a rendering and the installer a bundle
    carries beside it are one revision of the file.
    """

    def __init__(self, playbook_root: Path) -> None:
        self._script = playbook_root.joinpath(*_SCRIPT)
        self._loaded: tuple[bytes, ModuleType] | None = None

    def _module(self) -> tuple[bytes, ModuleType]:
        """The installer's bytes and the module loaded from them; scripts/ is not a package."""
        if not self._script.is_file():
            raise EntityNotFoundError("installer", "/".join(_SCRIPT))
        source = self._script.read_bytes()
        if self._loaded is not None and self._loaded[0] == source:
            return self._loaded
        spec = importlib.util.spec_from_file_location("_playbook_install_playbook", self._script)
        if spec is None or spec.loader is None:
            raise AppError(f"cannot load {self._script}")
        module = importlib.util.module_from_spec(spec)
        try:
            exec(compile(source, str(self._script), "exec"), module.__dict__)
        except SystemExit as exc:
            # The installer is a CLI. Importing one that does its work at module
            # level rather than under a __main__ guard would otherwise take the
            # request down with it; a refusal naming the file is recoverable.
            raise AppError(f"{self._script} exits when imported: {exc}") from exc
        if not hasattr(module, "AGENT_RUNTIMES"):
            raise AppError(f"{self._script} publishes no AGENT_RUNTIMES to render from")
        self._loaded = (source, module)
        logger.debug("Loaded agent renderings from %s", self._script)
        return self._loaded

    def runtimes(self) -> tuple:
        """Every harness the playbook renders for, in its own declared order."""
        return tuple(self._module()[1].AGENT_RUNTIMES)

    def render(self, *, raw: str, runtime: str) -> str:
        """Render one agent file for a named harness, or raise EntityNotFoundError."""
        for candidate in self.runtimes():
            if candidate.name == runtime:
                return candidate.render(raw)
        raise EntityNotFoundError("runtime", runtime)

    def installer_source(self) -> bytes:
        """The installer's own bytes: those the renderings come from.

        An install bundle carries it so the client applies the bundle with the
        installer's rules rather than a restatement of them.
        """
        return self._module()[0]
