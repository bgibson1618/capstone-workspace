# ADR taxonomy — local mirror (capstone-workspace)

> **What this is.** A LOCAL mirror of the project's ADR workstream taxonomy, kept here so the `/kb`
> slash command (`.claude/commands/kb.md`) can run inside this private workspace without working in the
> shared repo. It is **not** the canonical ADR index — the real ADRs live in the project repo at
> `~/projects/agent-memory-harness/docs/adrs/`. Keep the `## Naming convention` domain table below in
> sync with that file (re-copy when the project's taxonomy changes); the `/kb` command parses the four
> domain names from it and stops if they drift.
>
> Brent owns the **storage** domain (P3 — stores + router). Capstone's durable "why" record is
> `DECISION_LOG.md` (D001–D029); this dir exists for the `/kb` dependency + any ADR drafts Brent wants to
> stage privately before syncing to the project (`ADR-<domain>-NNN-<slug>.md`).

## Naming convention — by workstream domain

Files are named **`ADR-<domain>-NNN-<slug>.md`**, with **per-domain** sequential numbering. The four
domains map to the four parallel workstreams (mirrors
`~/projects/agent-memory-harness/docs/adrs/README.md`):

| Domain | Owner | Covers |
|---|---|---|
| **harness** | Keith (P1) | the Claude Code plugin (MCP · hooks · skills), log adapter, Daydreamer wiring, events stream, fail-open policy |
| **storage** | Brent (P3) | the Orchestrator / stores / router — the persistence + retrieval seam |
| **dreaming** | Scott B. (P4) | the two isolated subconscious functions — Daydreaming (in-session capture) and Dreaming (whole-store consolidation) — and the shared subconscious model |
| **eval** | Ken (P2) | the eval ↔ memory black-box boundary, package extraction, benchmark protocol |

Pick the domain by **which workstream owns the decision**, not where the code happens to sit today.

## Decision index

This local mirror tracks no ADRs of its own by default — capstone decisions are logged in
[`../../DECISION_LOG.md`](../../DECISION_LOG.md). Add `ADR-<domain>-NNN-<slug>.md` files here only if you
want to draft project ADRs from this workspace before syncing them upstream.
