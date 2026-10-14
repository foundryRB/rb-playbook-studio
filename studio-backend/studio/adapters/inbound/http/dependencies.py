"""Request dependencies for FastAPI routes: the container and the acting identity."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from studio.container import Container
from studio.domain.model.actor import Actor

__all__ = ["ActorDep", "ContainerDep", "get_actor", "get_container"]

_container: Container | None = None


def get_container() -> Container:
    """Return the shared Container singleton, creating it on first use."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def get_actor(request: Request) -> Actor | None:
    """Who this request acts as, as the gate resolved it (None: nobody trusted)."""
    return getattr(request.state, "actor", None)


ContainerDep = Annotated[Container, Depends(get_container)]
ActorDep = Annotated[Actor | None, Depends(get_actor)]
