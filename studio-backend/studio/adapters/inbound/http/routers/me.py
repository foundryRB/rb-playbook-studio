"""Identity routes: who you are on this door, and your own machine-door token."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from studio.adapters.inbound.http.dependencies import ActorDep, ContainerDep
from studio.adapters.inbound.http.dtos.personal_token_response import PersonalTokenResponse
from studio.adapters.inbound.http.dtos.standing_response import StandingResponse
from studio.adapters.inbound.http.personal_tokens import PersonalTokens
from studio.domain.exceptions.not_authenticated_error import NotAuthenticatedError

__all__ = ["router"]

router = APIRouter()


def _tokens(request: Request) -> PersonalTokens | None:
    return getattr(request.app.state, "personal_tokens", None)


@router.get("/me", response_model=StandingResponse)
def me(request: Request, container: ContainerDep, actor: ActorDep) -> StandingResponse:
    """Who you are, your role, the galaxies you write and the atoms you own.

    The UI renders every edit, create, sync and validate control from this and
    from each document's `can_edit`; it never reads OWNERS itself.
    """
    standing = container.get_standing().execute(actor=actor)
    tokens = _tokens(request)
    return StandingResponse(
        name=standing.actor.name,
        email=standing.actor.email,
        service=standing.actor.service,
        role=standing.role.value,
        galaxies=list(standing.galaxies),
        atoms=list(standing.atoms),
        can_edit_playbook=standing.can_edit_playbook,
        can_administer=standing.can_administer,
        can_validate=standing.can_validate,
        tokens=bool(tokens and tokens.enabled and not standing.actor.service),
    )


@router.post("/tokens", response_model=PersonalTokenResponse, status_code=201)
def mint_token(request: Request, actor: ActorDep) -> PersonalTokenResponse:
    """Mint a personal token for the signed-in person, shown this once.

    Every signed-in person may mint their own, a reader included: the token
    carries their identity to the machine door, and their rights stay whatever
    OWNERS gives them there.
    """
    if actor is None:
        raise NotAuthenticatedError()
    if actor.service:
        raise HTTPException(
            status_code=403,
            detail="personal tokens are for people; the service uses the shared credential",
        )
    tokens = _tokens(request)
    if tokens is None or not tokens.enabled:
        raise HTTPException(status_code=503, detail="personal tokens are not configured")
    token, claims = tokens.mint(actor)
    expires = datetime.fromtimestamp(claims.expires_at, tz=timezone.utc)
    return PersonalTokenResponse(
        token=token,
        email=claims.email,
        name=claims.name,
        expires_at=expires.isoformat().replace("+00:00", "Z"),
    )
