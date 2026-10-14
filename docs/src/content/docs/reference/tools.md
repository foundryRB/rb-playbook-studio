---
title: MCP tools
id: DOC-REF-TOOLS-001
type: Reference
status: Active
updated: "2026-10-12"
summary: "The studio's MCP tool surface: who a connection acts as, the corpus reads, the toolchain install, the gated writes, OWNERS, and the sync verbs, with the role each write needs."
---

The MCP server at `/mcp` exposes the same use cases as the SPA and the REST API, one tool per inbound port. Reads return parsed corpus content; writes run the playbook's own validation gates and roll back byte-identical when they fail; installs follow the client-executes idiom (the server returns files, the caller writes them).

A connection acts as whoever its credential names. A personal token (`Authorization: Bearer <token>`, minted from the studio's Connect menu) acts as its person, with the rights the playbook's `OWNERS` gives them, and every commit it causes names that person as its author. The shared HTTP Basic credential is the service's: it acts as the service and its commits name the service. `get_me` answers who the connection is and what it may do.

## Reads

Every document read carries `can_edit`: whether this connection may change that document.

| Tool | Returns |
| --- | --- |
| `get_me` | Who this connection acts as: name, email, whether it is the service, its role (admin, galaxy writer, atom owner, reader), the galaxies it may create in, the atoms it owns, and whether it may edit the playbook page, administer (OWNERS, sync) and run the gates. |
| `get_graph` | The full reference graph: playbook, galaxies, REFs, skills, agents, and their edges. |
| `get_playbook` | `AI-PLAYBOOK.md` parsed into titled sections. |
| `get_galaxy` | One galaxy's `GALAXY.md` (routing table, registries) parsed into titled sections. |
| `get_door` | One declared door's card (MCP or RAG): purpose and doctrine, never interface. |
| `get_ref` | One parsed REF by name: sections, domain, summary. |
| `get_skill` | One parsed skill: description, refs, file list, runtime state. |
| `get_skill_file` | One file from a skill folder: a UTF-8 file's text, or for any other file `{path, content, encoding}`, its bytes base64-encoded with `"encoding": "base64"` beside the path. Decode a base64 entry and write the decoded bytes. |
| `get_skill_files` | Every file of a skill as `{path, content}` entries, with `install_dir_hint` from the installer's metadata for `runtime` (`claude-code` by default, `opencode`, or `codex`). A UTF-8 file's text, or any other file's bytes base64-encoded with `"encoding": "base64"` beside the path. Decode a base64 entry before writing it. |
| `list_agents` | The whole agent roster: identity, licensed skills, doors, posture. |
| `get_agent` | One agent's parsed document. |
| `get_agent_files` | An agent's files rendered for a harness runtime, with filenames and directories from the installer: Codex gets `.toml`, Claude Code and OpenCode get `.md`. Omit `runtime` for all harnesses. |
| `list_claims` | Every intent claim the corpus declares. |
| `get_owners` | The playbook's `OWNERS` file as text, or null when it has none. |

## Toolchain install

| Tool | Returns |
| --- | --- |
| `get_install_command` | The one shell line that installs or refreshes every skill and agent for a named harness (`runtime`), for POSIX shells and for PowerShell, plus `skills_install_dir_hint` and `agents_install_dir_hint` from the installer. The line downloads one bundle with native agent filenames and runs the playbook's own installer against it, which prints a summary table; it carries a download-only token that expires in minutes, never the connector's credential. The line and the bundle URL name the studio's public origin, https on a deployment. |

## Gated writes

Each write first asks the rights: a write the connection's role does not reach is refused with a tool error naming the role it needs, and nothing is written. An allowed write runs the deterministic gates (intent tests plus the link checker) and restores the prior state byte-identical on failure; an accepted edit becomes one local git commit, authored by the connection's person (or the service).

| Tool | Writes | Needs |
| --- | --- | --- |
| `update_playbook_document` | `AI-PLAYBOOK.md` wholesale. | admin |
| `update_galaxy_document` | One galaxy's `GALAXY.md` wholesale. | that galaxy's writer, or admin |
| `update_ref_document` / `update_ref_section` | One REF wholesale, or one numbered section in place. | the REF's galaxy writer, or admin |
| `create_ref` | A new REF scaffolded onto a galaxy's shelf. | that galaxy's writer, or admin |
| `create_skill` / `create_agent` / `create_door` | A new skill, agent, or MCP or RAG card in a galaxy; `owners` (emails) become its owners in `OWNERS`. A card arrives whole (`raw`): frontmatter and doctrine. | that galaxy's writer, or admin |
| `update_agent_document` | One agent's document wholesale. | the agent's owner, its galaxy writer, or admin |
| `update_skill_document` / `update_skill_file` | A skill's `SKILL.md`, or one file in its folder (a new file included). | the skill's owner, its galaxy writer, or admin |
| `update_door_document` | One MCP or RAG card wholesale; it keeps its name. | the card's owner, its galaxy writer, or admin |
| `update_owners` | `OWNERS` wholesale. Refused when it does not parse or names a path the playbook does not hold; takes effect on the next request. | admin |
| `run_validation` | Nothing: runs the playbook's own validation suite over the working clone and returns the report. | any role that writes |

## Sync (managed-clone compositions only)

| Tool | Does | Needs |
| --- | --- | --- |
| `get_sync_status` | Unpushed commits, the diffstat a push would publish, and `repo`: the authoritative `owner/name` of the playbook repo itself. | anyone |
| `push_changes` | Publishes accumulated local commits upstream (rebase-retry on rejection); the service is the pusher. | admin |
| `refresh_content` | Pulls upstream head into the working clone. | admin |
