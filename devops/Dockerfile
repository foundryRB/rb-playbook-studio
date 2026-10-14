# syntax=docker/dockerfile:1

# Stage 1: build the React SPA. @psa-department-of-engineering/vitest-intent is
# on the public npm registry (csd-library ADR-0003), so this needs no .npmrc,
# no build secret, and no credential.
FROM node:22-slim AS web
WORKDIR /app/studio-frontend
COPY studio-frontend/package.json studio-frontend/package-lock.json ./
RUN npm ci
COPY studio-frontend ./
RUN npm run build

# Stage 2: runtime. One Python image serves the SPA, /api, and /mcp.
# git is a runtime dependency: the content repo is cloned onto the /data volume
# and every gated edit becomes a commit (ADR-001/ADR-002). The gates extra
# (pytest + pytest-intent) is a runtime dependency too: the playbook's own
# validation suite runs server-side on every mutation. Node is a runtime
# dependency for the same reason: that suite runs the deck layout gate with
# `node check-layouts.mjs`. The gate uses only node's built-in modules, so the
# runtime takes the node binary from the build stage (no npm, no second
# toolchain install), and `node --version` fails the build if it is ever dropped.
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    STUDIO_PLAYBOOK_ROOT=/data/playbook \
    STUDIO_GATES_USER=gates
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
# The gates run code the corpus carries, written by people who own a skill and
# nothing more, so they run as this unprivileged user: it owns the throwaway copy
# they judge, and cannot enter the clone or read the server's environment.
RUN useradd --system --user-group --no-create-home --shell /usr/sbin/nologin gates
COPY --from=web /usr/local/bin/node /usr/local/bin/node
RUN node --version
COPY studio-backend/pyproject.toml ./studio-backend/
COPY studio-backend/studio ./studio-backend/studio
RUN pip install --no-cache-dir -e "./studio-backend[gates]"
COPY --from=web /app/studio-frontend/dist ./studio-backend/web/dist
RUN mkdir -p /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health').read()" || exit 1
# --no-proxy-headers keeps the TCP peer the real one: the app trusts the OIDC
# sidecar's forwarded identity only from a loopback peer, and uvicorn would
# otherwise rewrite the peer from X-Forwarded-For.
CMD ["python", "-m", "uvicorn", \
     "studio.adapters.inbound.http.app:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
