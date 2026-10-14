"""One agent definition, rendered in a harness's own agent shape."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["RenderedAgent"]


@dataclass(frozen=True)
class RenderedAgent:
    """A corpus agent spelled the way one runtime reads it, ready to write.

    The corpus file is the definition; this is that definition in a harness's
    vocabulary (REF-Universe section 4). It carries where the file goes as well
    as what is in it, because a client installing it knows neither.
    """

    name: str
    runtime: str
    filename: str
    content: str
    install_dir_hint: str
