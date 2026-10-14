---
title: Decisions
id: DOC-DECISIONS-INDEX-001
type: Reference
status: Active
updated: "2026-10-09"
summary: "The decision log at a glance: which decisions are current, and which have been superseded."
---

Every architectural decision is recorded as an ADR. This index is the map: the current decisions, then the superseded ones kept for history. The records themselves carry the context and rationale.

## Current

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-001](../decisions/adr-001/) | Content pulled at runtime; git is the datastore | Decided |
| [ADR-002](../decisions/adr-002/) | Commit per gated edit, deliberate push | Decided |
| [ADR-003](../decisions/adr-003/) | Git behavior behind an outbound port, wired at the composition root | Decided |
| [ADR-004](../decisions/adr-004/) | MCP as an inbound adapter over the shared core | Decided |
| [ADR-006](../decisions/adr-006/) | OIDC for humans, HTTP Basic for MCP | Decided |
| [ADR-008](../decisions/adr-008/) | The loop engine is built here, carried by the playbook | Decided |
| [ADR-009](../decisions/adr-009/) | One download on the machine door, applied by the playbook's installer | Decided |
| [ADR-010](../decisions/adr-010/) | The human door learns who you are from the OIDC sidecar | Decided |
| [ADR-011](../decisions/adr-011/) | Rights come from OWNERS, decided by one function for both doors | Decided |
| [ADR-012](../decisions/adr-012/) | Personal tokens on the machine door; the shared credential is the service's | Decided |
| [ADR-013](../decisions/adr-013/) | Every commit names the person who made it | Decided |
| [ADR-014](../decisions/adr-014/) | One lock over the corpus, and writes off the event loop | Decided |

## Superseded

| ADR | Decision | Superseded by |
| --- | --- | --- |
| [ADR-005](../decisions/adr-005/) | Fail-closed HTTP Basic auth across SPA, API, and MCP | [ADR-006](../decisions/adr-006/) |
| [ADR-007](../decisions/adr-007/) | The toolchain installs in one download on the machine door | [ADR-009](../decisions/adr-009/) |
