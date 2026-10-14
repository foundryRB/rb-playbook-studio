---
title: Events
id: DOC-ARCH-EVENTS-001
type: Reference
status: Active
updated: "2026-10-09"
summary: "The facts the studio states on the platform event bus: one row per type under the playbook domain it owns, with the subject and the pointers each carries. The consumer's contract, held equal to the publisher by a test."
---

The studio owns the `playbook` domain on the platform's event bus by its own grant (the platform's `onboard-events` guide), and states one fact per mutation of the corpus. Every mutation already passes Trust Calibration (write, run the corpus gates, roll back byte-identical on failure), so each has exactly two outcomes and each is a fact: accepted and committed, or refused by a gate and rolled back. This page is the contract a consumer reads: the types, what each is about, and what `data` carries. It is held equal to the publisher's constants by the backend suite (`test_event_publishing.py`), so a row here is a type the studio emits and nothing else is.

Every event is a CloudEvent with `source` `/foundry/playbook-studio` and `datacontenttype` `application/json`. Each carries the document's identity and the commit message as its pointer, never the document's body: the corpus is the store, and a reader fetches from it by name. Publishing is one-way (`REF-Events` section 6): a publish that cannot be delivered is dropped and logged, and no edit's acceptance or rollback depends on the broker, which `INT-EVENTS-001` attests for every mutation below.

## The types

| Type | `subject` | Published when | `data` |
| --- | --- | --- | --- |
| `com.foundry.playbook.ref.created` | the REF name | a REF is scaffolded and the gates accept it | `ref`, `commit` |
| `com.foundry.playbook.ref.updated` | the REF name | a REF section or whole document is edited and the gates accept it | `ref`, `commit`, `section` (on a section edit) |
| `com.foundry.playbook.skill.created` | the skill name | a skill is scaffolded and the gates accept it | `skill`, `commit` |
| `com.foundry.playbook.skill.updated` | the skill name | a skill's SKILL.md or one of its files is edited and the gates accept it | `skill`, `commit`, `path` (on a file edit) |
| `com.foundry.playbook.agent.created` | the agent name | an agent is scaffolded and the gates accept it | `agent`, `commit` |
| `com.foundry.playbook.agent.updated` | the agent name | an agent document is replaced and the gates accept it | `agent`, `commit` |
| `com.foundry.playbook.playbook.updated` | `AI-PLAYBOOK.md` | the playbook index is replaced and the gates accept it | `playbook`, `commit` |
| `com.foundry.playbook.galaxy.updated` | the galaxy name | a galaxy's GALAXY.md is replaced and the gates accept it | `galaxy`, `commit` |
| `com.foundry.playbook.door.created` | the card name | an MCP or RAG card is filed and the gates accept it | `door`, `kind` (`mcp`, `rag`), `commit` |
| `com.foundry.playbook.door.updated` | the card name | an MCP or RAG card is replaced and the gates accept it | `door`, `kind` (`mcp`, `rag`), `commit` |
| `com.foundry.playbook.owners.updated` | `OWNERS` | an admin replaces `OWNERS` and the gates accept it | `owners`, `commit` |
| `com.foundry.playbook.validation.failed` | the document's name | a gate refuses a mutation and the clone is rolled back byte-identical | `target`, `kind` (`ref`, `skill`, `agent`, `mcp`, `rag`, `galaxy`, `playbook`, `owners`), `gates` (the refusing ones: `tests`, `links`) |
| `com.foundry.playbook.changes.pushed` | the repo slug | the studio's commits are pushed to the playbook's upstream | `repo` |

## What is not stated

Reads state nothing, and neither does a write the rights refuse: it never reaches the gates. The generated back-link sections are `sync_backlinks.py`'s output inside an accepted mutation and are not facts of their own. A refusal carries which gate refused and nothing of the gate's output; a consumer that needs the findings runs the validation itself.

Adding a type is one change to this page and to `studio/application/events.py` together; the test refuses either alone.
