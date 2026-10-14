# Playbook Studio

Management studio for the AI playbook: REF graph, gated edits, skill installs, MCP server

## Quickstart

Requires Node.js 22.12 or newer.

```bash
npm install
npm run dev          # http://localhost:4321
```

## Scripts

| Command            | Action                                                   |
| -------------------- | ---------------------------------------------------------- |
| `npm run dev`      | Start local dev server                                   |
| `npm run build`    | Run `astro check` + production build                     |
| `npm run preview`  | Preview the production build locally                     |
| `npm run test`     | Run vitest (STARLIGHT bundle frontmatter claims)         |
| `npm run lint:md`  | Lint Markdown content                                    |

## Structure

```
.
├── astro.config.mjs       # Starlight configuration
├── src/
│   ├── content.config.ts # Content collection schema (frontmatter validation)
│   ├── content/
│   │   └── docs/         # All site content
│   └── styles/
│       └── custom.css     # Site-specific overrides (the shared theme comes from the package)
├── tests/
│   └── starlight.test.ts     # STARLIGHT bundle frontmatter claims (--no-intent skips)
├── intent.yaml               # CSD intent claims (from STARLIGHT bundle)
└── public/                # Static assets
```

## Authoring rules

- Use Markdown by default; MDX only when components are needed (per `REF-StarlightDocs.md` §3 in the playbook).
- Every doc page requires frontmatter with: `title`, `id`, `type`, `status`, `updated`. Schema enforces this at build time.
- Add sidebar entries in `astro.config.mjs` for new top-level sections; nested folders auto-generate.

## Scaffolded by

`bootstrap-starlight` skill — see `skills/bootstrap-starlight/SKILL.md` in the playbook.
