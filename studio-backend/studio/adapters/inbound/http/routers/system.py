"""System routes: health, version, and the agent connect credential."""

from __future__ import annotations

import base64
import os

from fastapi import APIRouter, HTTPException

from studio import __version__
from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.health_response import HealthResponse

__all__ = ["router"]

router = APIRouter()


def _served_version() -> str:
    """The release actually running, for the delivery evidence chain.

    $APP_VERSION is the chart's image tag - the value promotion writes back - so
    the answer describes the pod rather than the source tree. The package
    constant is the local-dev fallback only: semantic-release never rewrites it,
    so on its own it is a hardcoded string, which is not freshness.
    """
    return os.environ.get("APP_VERSION") or __version__


@router.get("/health", response_model=HealthResponse)
async def health(container: ContainerDep) -> HealthResponse:
    """Report service liveness, the served release, and wired capabilities.

    Reachable unauthenticated on every door: the kubelet probes it bare, and the
    OIDC sidecar skips it so an external observer can read which release serves
    without a credential.
    """
    return HealthResponse(status="ok", version=_served_version(), sync=container.sync_enabled)


@router.get("/agent-credential")
async def agent_credential(actor: ActorDep) -> dict:
    """The shared MCP HTTP Basic credential (base64 of user:password), handed back
    only to a caller that already acts as the service.

    The shared credential is the service's: a person connects an agent with
    their own personal token (POST /api/tokens). So the route answers only on
    the stand-alone deployment, where the human door's Basic gate means the
    caller already holds this very pair; behind the OIDC proxy a person gets a
    403. Answers 503 when the pair is unset (there is nothing to hand out).
    """
    if actor is None or not actor.service:
        raise HTTPException(
            status_code=403,
            detail="the shared credential is for services; mint your own token instead",
        )
    user = os.environ.get("STUDIO_AUTH_USER", "")
    password = os.environ.get("STUDIO_AUTH_PASSWORD", "")
    if not (user and password):
        raise HTTPException(status_code=503, detail="MCP credential is not configured")
    encoded = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"credential": encoded}
