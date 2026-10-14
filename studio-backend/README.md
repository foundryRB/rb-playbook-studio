# studio-backend

Local visual browser and editor for the AI playbook: REF graph, section detail, gated edits.

A Python FastAPI service in hexagonal (ports and adapters) architecture, scaffolded
by the bootstrap-hexagonal-backend skill.

## Develop

Create a venv, install, lint, test (POSIX paths shown; on Windows use
`.venv\Scripts\python.exe`):

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python -m studio.adapters.inbound.http.run
```

## Export the OpenAPI contract

```bash
.venv/bin/python scripts/export_openapi.py   # writes openapi.json
```

## Layout

- `studio/domain` - entities, value objects, exceptions (no outward imports)
- `studio/application` - inbound/outbound ports and use cases
- `studio/adapters` - HTTP inbound adapter and outbound adapters
- `studio/container.py` - composition root
