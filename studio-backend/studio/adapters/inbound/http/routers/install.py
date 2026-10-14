"""Install routes: the whole toolchain in one download, on the machine door.

They live under /mcp/install/{token}/ because /mcp is where machine credentials
already pass: the OIDC proxy in front of the human surfaces skips it, and the
app's own gate admits the download token in the path (auth.py). The token in the
path has been checked by the time a handler runs. None of these routes is part
of the REST contract, so none is in the OpenAPI schema.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from studio.adapters.inbound.http.dependencies import ContainerDep
from studio.adapters.inbound.http.installer import bundle_archive, install_script, public_base

__all__ = ["router"]

router = APIRouter()

_SCRIPTS = ("install.sh", "install.ps1")


@router.get("/install/{token}/bundle.tar.gz", include_in_schema=False)
def get_bundle(token: str, runtime: str, container: ContainerDep) -> Response:
    """Every skill and every agent rendered for `runtime`, with the manifest and the
    playbook installer, as one gzipped tar."""
    bundle = container.get_install_bundle().execute(runtime=runtime)
    return Response(content=bundle_archive(bundle), media_type="application/gzip")


@router.get("/install/{token}/{script}", include_in_schema=False)
def get_install_script(
    token: str, script: str, runtime: str, request: Request, container: ContainerDep
) -> PlainTextResponse:
    """The install script for one shell, pointed at this token's bundle for `runtime`."""
    if script not in _SCRIPTS:
        raise HTTPException(status_code=404, detail=f"no install script {script!r}")
    runtimes = tuple(r.name for r in container.list_agent_runtimes().execute())
    if runtime not in runtimes:
        raise HTTPException(
            status_code=404,
            detail=f"unknown runtime {runtime!r}; this playbook renders for: {', '.join(runtimes)}",
        )
    try:
        base = public_base(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    bundle_url = f"{base}/mcp/install/{token}/bundle.tar.gz?runtime={runtime}"
    return PlainTextResponse(install_script(script, bundle_url))
