"""MCP inbound adapter: tools mirroring the inbound ports (streamable HTTP).

A third door into the same use cases as the SPA and REST: every write goes
through the identical rights-check, gate-validate-rollback-commit path
(ADR-004), as whoever the gate resolved the request to (a person's personal
token, or the service's shared credential). The tool list derives from the
capability wiring, so the sync tools exist only when the composition manages
the clone.

Write tools run their use case on a worker thread: a gated write runs the
playbook's whole validation, and on the event loop it would stall every other
route, the health check included.

Serialization reuses the HTTP DTO mappers: the OpenAPI contract is the studio's
single serialization surface, and the MCP tools mirror it mechanically rather
than maintaining a parallel shape.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Callable
from functools import partial
from typing import Any, TypeVar

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from studio.adapters.inbound.http.download_tokens import DOWNLOAD_PREFIX, DownloadTokens
from studio.adapters.inbound.http.installer import public_base
from studio.adapters.inbound.http.mappers.agent_mapper import map_agent
from studio.adapters.inbound.http.mappers.claim_mapper import map_claim
from studio.adapters.inbound.http.mappers.door_mapper import map_door
from studio.adapters.inbound.http.mappers.galaxy_mapper import map_galaxy
from studio.adapters.inbound.http.mappers.graph_mapper import map_graph
from studio.adapters.inbound.http.mappers.playbook_mapper import map_playbook
from studio.adapters.inbound.http.mappers.ref_mapper import map_ref
from studio.adapters.inbound.http.mappers.skill_mapper import map_skill
from studio.adapters.inbound.http.mappers.sync_mapper import map_sync_status
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.container import Container
from studio.domain.exceptions.forbidden_error import ForbiddenError
from studio.domain.exceptions.invalid_owners_error import InvalidOwnersError
from studio.domain.exceptions.not_authenticated_error import NotAuthenticatedError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action
from studio.domain.model.validation_report import ValidationReport

__all__ = ["build_mcp_server"]

_T = TypeVar("_T")

_INSTRUCTIONS = (
    "Management surface for the AI playbook (REFs, skills, agents, intent "
    "claims). Reads return parsed corpus content; writes are gated by the "
    "playbook's own validation suite and roll back byte-identical when the "
    "gates fail. Every write acts as whoever your credential names: a personal "
    "token acts as its person, with the rights the playbook's OWNERS gives them, "
    "and a refused write names the role it needs (get_me says who you are and "
    "what you may do). Installs follow the client-executes idiom: the server serves, "
    "your machine writes. To install or refresh the whole toolchain, call "
    "get_install_command with the harness this session runs in and run the "
    "line it returns once: one download, applied by the playbook's own "
    "installer, and a summary table is all you read back. For one skill or one "
    "agent, get_skill_files "
    "and get_agent_files return the files, already rendered for your harness, "
    "and YOU write them into your runtime skills and agents directories - "
    "never hand-render an agent's fields yourself."
)

_ALLOWED_HOSTS_ENV = "STUDIO_MCP_ALLOWED_HOSTS"


def _skill_file_entry(rel_path: str, data: bytes) -> dict[str, str]:
    """One skill file as the tools carry it: its text when the bytes are UTF-8,
    otherwise the bytes base64-encoded, marked so the client decodes them."""
    try:
        return {"path": rel_path, "content": data.decode("utf-8")}
    except UnicodeDecodeError:
        encoded = base64.b64encode(data).decode("ascii")
        return {"path": rel_path, "content": encoded, "encoding": "base64"}


def _transport_security() -> TransportSecuritySettings | None:
    """DNS-rebinding protection for the transport.

    The SDK default admits localhost only, which is right for the local run.
    A deployment serves on a public hostname, so the chart supplies it via
    $STUDIO_MCP_ALLOWED_HOSTS (comma-separated Host header values).
    """
    raw = os.environ.get(_ALLOWED_HOSTS_ENV)
    if not raw:
        return None
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    return TransportSecuritySettings(allowed_hosts=hosts)


def _actor(ctx: Context) -> Actor | None:
    """Who this call acts as, as the HTTP gate resolved it."""
    request = ctx.request_context.request
    return getattr(request.state, "actor", None) if request is not None else None


async def _act(ctx: Context, use_case: Callable[..., _T], /, **kwargs: Any) -> _T:
    """Run a use case as the caller, off the event loop; refusals become tool errors."""
    call = partial(use_case, actor=_actor(ctx), **kwargs)
    try:
        return await anyio.to_thread.run_sync(call)
    except ValidationFailedError as exc:
        raise ToolError(_rejection(exc)) from exc
    except (ForbiddenError, NotAuthenticatedError, InvalidOwnersError) as exc:
        raise ToolError(str(exc)) from exc


def _report_text(report: ValidationReport) -> str:
    return (
        f"tests_passed={report.tests_passed} links_ok={report.links_ok}\n"
        f"{report.tests_output}\n{report.links_output}"
    )


def _gated(report: ValidationReport) -> dict[str, object]:
    return map_validation_report(report).model_dump()


def build_mcp_server(container: Container, download_tokens: DownloadTokens) -> FastMCP:
    """Build the MCP server over the container's wired use cases.

    `download_tokens` mints the credential an install command carries; the HTTP
    gate holds the same instance to admit it.
    """
    server = FastMCP(
        "playbook-studio",
        instructions=_INSTRUCTIONS,
        streamable_http_path="/",
        stateless_http=True,
        transport_security=_transport_security(),
    )

    @server.tool()
    def get_graph() -> dict[str, object]:
        """Return the full playbook reference graph (playbook, REFs, skills, agents, edges)."""
        return map_graph(container.get_graph().execute()).model_dump()

    def may_edit(ctx: Context, path: str) -> bool:
        return container.rights().may(_actor(ctx), Action.EDIT, path)

    @server.tool()
    def get_me(ctx: Context) -> dict[str, object]:
        """Return who this connection acts as and what OWNERS lets it do.

        `role` is admin, galaxy writer, atom owner or reader; `galaxies` are the
        galaxies you may create in, `atoms` the atoms you own by name. A personal
        token acts as its person; the shared credential acts as the service.
        """
        standing = container.get_standing().execute(actor=_actor(ctx))
        return {
            "name": standing.actor.name,
            "email": standing.actor.email,
            "service": standing.actor.service,
            "role": standing.role.value,
            "galaxies": list(standing.galaxies),
            "atoms": list(standing.atoms),
            "can_edit_playbook": standing.can_edit_playbook,
            "can_administer": standing.can_administer,
            "can_validate": standing.can_validate,
        }

    @server.tool()
    def get_playbook(ctx: Context) -> dict[str, object]:
        """Return AI-PLAYBOOK.md parsed into titled sections."""
        doc = container.get_playbook().execute()
        return map_playbook(doc, can_edit=may_edit(ctx, "AI-PLAYBOOK.md")).model_dump()

    @server.tool()
    def get_galaxy(name: str, ctx: Context) -> dict[str, object]:
        """Return one galaxy's GALAXY.md (routing table, registries) parsed into titled sections."""
        galaxy = container.get_galaxy().execute(name=name)
        return map_galaxy(galaxy, can_edit=may_edit(ctx, galaxy.path)).model_dump()

    @server.tool()
    def get_door(name: str, ctx: Context) -> dict[str, object]:
        """Return one declared door's card (MCP or RAG): purpose and doctrine, never interface."""
        door = container.get_door().execute(name=name)
        return map_door(door, can_edit=may_edit(ctx, door.path)).model_dump()

    @server.tool()
    def get_ref(name: str, ctx: Context) -> dict[str, object]:
        """Return one parsed REF by name (e.g. REF-Python): sections, domain, summary."""
        ref = container.get_ref().execute(name=name)
        return map_ref(ref, can_edit=may_edit(ctx, ref.path)).model_dump()

    @server.tool()
    def get_skill(name: str, ctx: Context) -> dict[str, object]:
        """Return one parsed skill: description, refs, file list, runtime state."""
        skill = container.get_skill().execute(name=name)
        status = container.get_skill_status().execute(name=name)
        return map_skill(skill, status, can_edit=may_edit(ctx, skill.path)).model_dump()

    @server.tool()
    def get_skill_file(name: str, rel_path: str) -> str | dict[str, str]:
        """Return one file from a skill folder.

        A UTF-8 file comes back as its text. Any other file comes back as
        {path, content, encoding}: its bytes base64-encoded, with
        "encoding": "base64" beside the path. Decode that content and write the
        decoded bytes, never the base64 text.
        """
        entry = _skill_file_entry(
            rel_path, container.get_skill_file().execute(name=name, rel_path=rel_path)
        )
        return entry if "encoding" in entry else entry["content"]

    @server.tool()
    def get_skill_files(name: str, runtime: str = "claude-code") -> dict[str, object]:
        """Return every file of a skill for a client-side install.

        The server owns the corpus; effects on your machine are yours. Write
        each file under the returned install_dir_hint/<path>. Name your harness
        in `runtime` ("claude-code", "opencode", or "codex"); omission keeps
        the Claude Code default. A UTF-8 file's content is
        its text; write it as UTF-8, unchanged. Any other file, such as a
        template or an image, carries "encoding": "base64" beside its path:
        decode its content and write the decoded bytes, never the base64 text.
        """
        runtimes = {r.name: r for r in container.list_agent_runtimes().execute()}
        if runtime not in runtimes:
            raise ToolError(
                f"unknown runtime {runtime!r}; this playbook renders for: " + ", ".join(runtimes)
            )
        skill = container.get_skill().execute(name=name)
        files = [
            _skill_file_entry(
                rel_path, container.get_skill_file().execute(name=name, rel_path=rel_path)
            )
            for rel_path in skill.files
        ]
        return {
            "name": skill.name,
            "install_dir_hint": f"{runtimes[runtime].skills_install_hint}{skill.name}/",
            "files": files,
        }

    @server.tool()
    def list_agents(ctx: Context) -> list[dict[str, object]]:
        """Return the whole agent roster: identity, licensed skills, doors, posture."""
        return [
            map_agent(a, can_edit=may_edit(ctx, a.path)).model_dump()
            for a in container.list_agents().execute()
        ]

    @server.tool()
    def get_agent(name: str, ctx: Context) -> dict[str, object]:
        """Return one parsed agent: identity, licence, doors, posture, appearance."""
        agent = container.get_agent().execute(name=name)
        return map_agent(agent, can_edit=may_edit(ctx, agent.path)).model_dump()

    @server.tool()
    def get_agent_files(name: str, runtime: str | None = None) -> dict[str, object]:
        """Return one agent already rendered for the harness that will run it.

        The roster's counterpart to get_skill_files, and the same client-executes
        idiom: the server renders, you write. Each entry carries the file name,
        its content, and the directory that harness reads agents from. Omit
        `runtime` to get every rendering and write the one your harness uses;
        name it ("claude-code", "opencode", "codex") to get just that one. Never spell an
        agent's fields yourself - the rendering is the playbook installer's, and
        a hand-made copy is the drift this tool exists to remove.
        """
        rendered = container.get_agent_files().execute(name=name, runtime=runtime)
        return {
            "name": name,
            "agents": [
                {
                    "runtime": r.runtime,
                    "filename": r.filename,
                    "install_dir_hint": r.install_dir_hint,
                    "content": r.content,
                }
                for r in rendered
            ],
        }

    @server.tool()
    def get_install_command(runtime: str, ctx: Context) -> dict[str, object]:
        """Return the one shell line that installs or refreshes the whole toolchain.

        Name the harness this session runs in (`runtime`, e.g. "claude-code" or
        "opencode", or "codex"). Run the line for your shell once: `posix` on Linux, macOS,
        or Git Bash; `powershell` on Windows PowerShell or pwsh. It downloads
        every skill and every agent rendered for that harness as one archive and
        runs the playbook's own installer against it: only what differs is
        written, each skill folder is swapped in whole, and nothing is deleted
        unless you append --prune. Directory overrides append the same way
        (--runtime-dir, --agents-dir, --opencode-agents-dir,
        --codex-skills-dir, --codex-agents-dir). It prints one
        summary table, and a note to restart the session when anything changed;
        relay both. It needs Python 3.8 or newer on the machine. The line
        carries a download-only token that expires after `expires_in_seconds`,
        never this connector's credential; ask again for a fresh one.
        """
        runtimes = {r.name: r for r in container.list_agent_runtimes().execute()}
        if runtime not in runtimes:
            raise ToolError(
                f"unknown runtime {runtime!r}; this playbook renders for: {', '.join(runtimes)}"
            )
        request = ctx.request_context.request
        if request is None:
            raise ToolError("get_install_command needs the HTTP transport to name its host")
        try:
            base = public_base(request)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        root = f"{base}{DOWNLOAD_PREFIX}{download_tokens.mint()}"
        return {
            "runtime": runtime,
            "skills_install_dir_hint": runtimes[runtime].skills_install_hint,
            "agents_install_dir_hint": runtimes[runtime].install_hint,
            "posix": f"curl -fsSL '{root}/install.sh?runtime={runtime}' | sh -s --",
            "powershell": (
                f"& ([scriptblock]::Create((irm '{root}/install.ps1?runtime={runtime}')))"
            ),
            "expires_in_seconds": download_tokens.ttl_seconds,
        }

    @server.tool()
    def list_claims() -> list[dict[str, object]]:
        """Return every claim in the playbook's intent.yaml."""
        return [map_claim(c).model_dump() for c in container.list_claims().execute()]

    @server.tool()
    async def run_validation(ctx: Context) -> dict[str, object]:
        """Run the playbook's intent tests + link checker and return the report."""
        return _gated(await _act(ctx, container.run_validation().execute))

    @server.tool()
    def get_owners() -> dict[str, object]:
        """Return the playbook's OWNERS file: who may change what (null when absent).

        CODEOWNERS syntax: a path anchored at the root, then the owners' emails. A
        person may change a path a line gives them, or anything under it;
        `not-before <email> <date>` refuses the personal tokens issued to that
        person before the date.
        """
        return {"raw": container.get_owners().execute()}

    @server.tool()
    async def update_owners(raw: str, ctx: Context) -> dict[str, object]:
        """Replace OWNERS (admins only). Refused when it does not parse or names a
        path the playbook does not hold; takes effect on the next request."""
        return _gated(await _act(ctx, container.update_owners().execute, raw=raw))

    @server.tool()
    async def update_playbook_document(raw: str, ctx: Context) -> dict[str, object]:
        """Replace AI-PLAYBOOK.md; the edit survives only if the gates pass."""
        return _gated(await _act(ctx, container.update_playbook_document().execute, raw=raw))

    @server.tool()
    async def update_galaxy_document(name: str, raw: str, ctx: Context) -> dict[str, object]:
        """Replace a galaxy's GALAXY.md; the edit survives only if the gates pass.

        The Available Skills table is generated by the playbook's own
        scripts/sync_registry.py: send it back exactly as get_galaxy returned it,
        or the gates refuse the write.
        """
        use_case = container.update_galaxy_document().execute
        return _gated(await _act(ctx, use_case, name=name, raw=raw))

    @server.tool()
    async def update_ref_section(
        ref_name: str, number: int, body: str, ctx: Context
    ) -> dict[str, object]:
        """Write one REF section body; the edit survives only if the gates pass."""
        use_case = container.update_ref_section().execute
        return _gated(await _act(ctx, use_case, ref_name=ref_name, number=number, body=body))

    @server.tool()
    async def update_ref_document(ref_name: str, raw: str, ctx: Context) -> dict[str, object]:
        """Replace a whole REF document; the edit survives only if the gates pass."""
        use_case = container.update_ref_document().execute
        return _gated(await _act(ctx, use_case, ref_name=ref_name, raw=raw))

    @server.tool()
    async def create_ref(
        name: str, domain: str, title: str, summary: str, ctx: Context, galaxy: str = "craft"
    ) -> dict[str, object]:
        """Author a new REF from the canonical template; gated like every edit."""
        ref = await _act(
            ctx,
            container.create_ref().execute,
            name=name,
            domain=domain,
            title=title,
            summary=summary,
            galaxy=galaxy,
        )
        return map_ref(ref, can_edit=may_edit(ctx, ref.path)).model_dump()

    @server.tool()
    async def create_skill(
        name: str,
        description: str,
        refs: list[str],
        ctx: Context,
        galaxy: str = "craft",
        owners: list[str] | None = None,
    ) -> dict[str, object]:
        """Scaffold a new skill via bootstrap-skill; gated like every edit.

        `owners` (emails) become the skill's owners in OWNERS."""
        skill = await _act(
            ctx,
            container.create_skill().execute,
            name=name,
            description=description,
            refs=refs,
            galaxy=galaxy,
            owners=owners,
        )
        status = container.get_skill_status().execute(name=skill.name)
        return map_skill(skill, status, can_edit=may_edit(ctx, skill.path)).model_dump()

    @server.tool()
    async def create_agent(
        name: str,
        title: str,
        description: str,
        refs: list[str],
        skills: list[str],
        ctx: Context,
        doors: list[str] | None = None,
        galaxy: str = "craft",
        permission: str | None = None,
        writes: bool = False,
        fresh_eyes: bool = False,
        hair: str | None = None,
        headwear: str | None = None,
        eyes: str | None = None,
        face: str | None = None,
        owners: list[str] | None = None,
    ) -> dict[str, object]:
        """Scaffold a new agent via bootstrap-agent; gated like every edit.

        ``description`` is the one line a harness routes work by; ``title`` is
        the job title the room draws and the run log names. ``owners`` (emails)
        become the agent's owners in OWNERS."""
        agent = await _act(
            ctx,
            container.create_agent().execute,
            name=name,
            title=title,
            description=description,
            refs=refs,
            skills=skills,
            doors=doors,
            galaxy=galaxy,
            permission=permission,
            writes=writes,
            fresh_eyes=fresh_eyes,
            hair=hair,
            headwear=headwear,
            eyes=eyes,
            face=face,
            owners=owners,
        )
        return map_agent(agent, can_edit=may_edit(ctx, agent.path)).model_dump()

    @server.tool()
    async def update_agent_document(name: str, raw: str, ctx: Context) -> dict[str, object]:
        """Replace a whole agent document; the edit survives only if the gates pass."""
        use_case = container.update_agent_document().execute
        return _gated(await _act(ctx, use_case, name=name, raw=raw))

    @server.tool()
    async def create_door(
        kind: str,
        name: str,
        galaxy: str,
        raw: str,
        ctx: Context,
        owners: list[str] | None = None,
    ) -> dict[str, object]:
        """File a new MCP card (`kind` "mcp") or RAG card ("rag") in a galaxy; gated
        like every edit.

        `raw` is the whole card: frontmatter (name, galaxy, refs) and the earned
        doctrine, never the server's interface or a binding. `owners` (emails)
        become the card's owners in OWNERS."""
        door = await _act(
            ctx,
            container.create_door().execute,
            kind=kind,
            name=name,
            galaxy=galaxy,
            raw=raw,
            owners=owners,
        )
        return map_door(door, can_edit=may_edit(ctx, door.path)).model_dump()

    @server.tool()
    async def update_door_document(name: str, raw: str, ctx: Context) -> dict[str, object]:
        """Replace a whole MCP or RAG card; the edit survives only if the gates pass."""
        use_case = container.update_door_document().execute
        return _gated(await _act(ctx, use_case, name=name, raw=raw))

    @server.tool()
    async def update_skill_document(name: str, raw: str, ctx: Context) -> dict[str, object]:
        """Replace a whole SKILL.md; the edit survives only if the gates pass."""
        use_case = container.update_skill_document().execute
        return _gated(await _act(ctx, use_case, name=name, raw=raw))

    @server.tool()
    async def update_skill_file(
        name: str, rel_path: str, content: str, ctx: Context
    ) -> dict[str, object]:
        """Write one skill file, creating it when the skill does not carry it yet.

        This is how a skill grows the templates, scripts, and reference pages it
        ships beside SKILL.md. The write survives only if the gates pass; a
        rejected creation leaves the skill folder as it was.
        """
        use_case = container.update_skill_file().execute
        return _gated(await _act(ctx, use_case, name=name, rel_path=rel_path, content=content))

    if container.sync_enabled:

        @server.tool()
        def get_sync_status() -> dict[str, object]:
            """Report unpushed commits, the diffstat a push would publish, and
            `repo` - the `owner/name` of the playbook repo itself.

            `repo` is the authoritative answer to "which repo IS the playbook?",
            read from the clone this door owns and pushes to. Any act that must
            target the playbook repo (filing a proposed REF or skill change as a
            ticket, say) asks here rather than guessing from a repo's name or
            carrying a literal that a rename or org move would strand. This
            door's own app repo is NOT the playbook repo - it serves the corpus,
            it does not contain it. Empty means this composition has no
            upstream (a local run); treat that as unknown, never as a default.
            """
            return map_sync_status(container.get_sync_status().execute()).model_dump()

        @server.tool()
        async def push_changes(ctx: Context) -> dict[str, object]:
            """Publish accumulated local commits upstream (rebase-retry on rejection).
            An admin's act."""
            status = await _act(ctx, container.push_changes().execute)
            return map_sync_status(status).model_dump()

        @server.tool()
        async def refresh_content(ctx: Context) -> dict[str, object]:
            """Pull upstream head into the working clone. An admin's act."""
            status = await _act(ctx, container.refresh_content().execute)
            return map_sync_status(status).model_dump()

    return server


def _rejection(exc: ValidationFailedError) -> str:
    return "edit rejected by the validation gates (rolled back):\n" + _report_text(exc.report)
