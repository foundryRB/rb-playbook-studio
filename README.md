# Playbook Studio

Management studio for the AI playbook (the private `playbook` repo): a radial reference graph of the corpus (playbook at the center, REFs clustered by domain, the planets - skills, agents, doors - on the outer ring), section-level reading and editing, skill and agent management, and an MCP server so agents can do all of it too.

Every mutation applies CSD Trust Calibration to the playbook itself: the edit is written, the playbook's own deterministic gates run (intent-test suite + link checker), and the edit is **rolled back byte-identical** if any gate fails. An accepted edit becomes a git commit; a deliberate push publishes accumulated commits. The machine-generated "Skills that instantiate this REF" sections are read-only (HTTP 409 on write) - they belong to `scripts/sync_backlinks.py`.

One deployment serves three doors over the same use cases: the SPA at `/`, the REST API at `/api`, and the MCP server at `/mcp`, with OIDC via oauth2-proxy for the SPA and REST API and fail-closed HTTP Basic auth for MCP in the default deployment. Local runs and deployments with OIDC disabled use HTTP Basic auth across all three doors. Architecture and decisions live in `docs/` (Starlight; ADRs under Decisions).

People act as themselves on both doors: the person the OIDC proxy signs in on the human door, the person a personal token names on the machine door. What each may change comes from the playbook's own `OWNERS` file (CODEOWNERS syntax: admins own `/`, galaxy writers `galaxies/<name>/`, atom owners one skill, agent or card; everyone else reads), and every commit names the person who made it. Without an `OWNERS` file every person reads and nobody writes. The shared Basic credential acts as the service.

## Layout

- `studio-backend/` - Python FastAPI service, hexagonal (see its README). The domain is the playbook: `RefDoc`, `SkillDoc`, `AgentDoc`, `IntentClaim`, `ReferenceEdge`, `ValidationReport`, `SyncStatus`.
- `studio-frontend/` - React + TypeScript MVVM SPA typed from the backend's `openapi.json`.
- `docs/` - Starlight docs site (architecture pages + ADRs), served behind the central docs portal.
- `devops/` - Dockerfile (multi-stage: SPA build + Python runtime) and docker-compose.
- `k8s/` - Helm chart; `k8s/secrets/*.env.example` document the out-of-band Secrets.

## Run with docker

```bash
docker compose -f devops/docker-compose.yml up --build
```

Serves everything on http://localhost:8000 (credentials in the compose file; change them, or set `STUDIO_CONTENT_REPO_URL` for the managed-clone composition). Building the SPA stage installs the `@psa-department-of-engineering/*` packages from the public npm registry, so the build needs no token or build secret.

## Develop without docker

Double-click `devops/start.bat` (or `powershell -ExecutionPolicy Bypass -File devops/start.ps1`). The first run provisions everything (backend venv + deps + the gates toolchain, frontend `npm ci` + generated API types); every run spawns the two server windows and opens http://localhost:5199. Close the windows to stop.

Manual equivalent: backend `PORT=8907` via `studio-backend/.venv/Scripts/python -m studio.adapters.inbound.http.run`, frontend `npm run dev -- --port 5199` (the dev proxy expects the backend on `127.0.0.1:8907`). The playbook location defaults to the sibling `../../playbook`; override with `STUDIO_PLAYBOOK_ROOT`. Locally the git adapter is a no-op: the studio edits the working tree and you commit yourself.

## Connect an agent

Open the Connect menu in the studio's header and mint your own token, then:

```bash
claude mcp add --scope user --transport http playbook https://<host>/mcp --header "Authorization: Bearer <your-token>"
```

The agent acts as you: it reads everything and writes what `OWNERS` lets you, and a write beyond that is refused with the role it needs. A token expires (90 days by default) and an admin revokes the tokens issued to someone with a `not-before` line in `OWNERS`. Services connect the same way with the shared credential (`Authorization: Basic <credential>`) and act as the service. Personal tokens need `STUDIO_TOKEN_KEY`, and the human door's forwarded identity needs `STUDIO_PROXY_SECRET`, both in the app's auth Secret (`k8s/secrets/playbook-studio-auth.env.example`).

Tools mirror the API: reads (graph, playbook, REFs, skills, agents, claims, validation), gated writes (MCP and RAG cards and `OWNERS` included), `get_me`, skill file delivery for client-side installs, the one-line toolchain install (`get_install_command`: one bundle under `/mcp/install/`, fetched with a short-lived download token and applied by the playbook's own installer), and (deployed) sync status/push/refresh. One deliberate exception: the corpus's `nebulae/` zone (unearned research) is HTTP-only at `/api/nebulae`; the quarantine (REF-Forge) keeps stardust off the machine door and out of the graph.

## Intent claims (CSD)

The studio eats its own dog food: `intent.yaml` at this root declares the claims (gated writes roll back, generated sections immutable, creation delegates to the playbook's own bootstrap skills, graph fidelity, layout invariants, commit-per-gated-edit, MCP parity, fail-closed auth). Backend tests carry `@intent` (pytest-intent), frontend tests carry `intent()` (vitest-intent). Audit both in one pass:

```bash
studio-backend/.venv/Scripts/csd-intent .
```

## Contract sync

After any backend DTO or route change: `.venv/Scripts/python scripts/export_openapi.py` in `studio-backend`, copy `openapi.json` to `studio-frontend/src/models/`, then `npm run api:generate` in `studio-frontend` (or `npm run api:sync` against a running backend).

## Commits

Every commit follows the platform's commit convention: a Conventional Commit
subject and no co-author trailer. CI derives the version from the type and
blocks release otherwise. The convention is documented on the platform
portal's GitOps delivery page, under "Commit convention"; the committed
`.pre-commit-config.yaml` checks it locally once installed (`pre-commit install`).
