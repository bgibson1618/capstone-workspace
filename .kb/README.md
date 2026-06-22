# Project Knowledge Base — capstone mirror

> **Capstone-local KB.** This is the PRIVATE mirror of the team's project-story journal, kept in the
> capstone planning workspace so storage-domain entries can be drafted here (via the vendored `/kb`
> command) without working in the shared repo. Sync entries into the project's `.kb/KB-<domain>.md` when
> sharing. The canonical KB + ADRs live in `~/projects/agent-memory-harness/`.

One append-only file per workstream domain. Entries are timestamped checkpoints of project state — context
that doesn't belong in code, ADRs, or PRs but is worth preserving across the sprint. The four domains
mirror [`../docs/adrs/README.md`](../docs/adrs/README.md):

| Domain | Owner | File |
|---|---|---|
| **harness**  | Keith | KB-harness.md   |
| **storage**  | Brent | [KB-storage.md](KB-storage.md) |
| **dreaming** | Scott | KB-dreaming.md  |
| **eval**     | Ken   | KB-eval.md      |

(In this capstone mirror, only the **storage** journal is expected — Brent's domain.)

## Conventions

- **Append-only.** Each entry is a snapshot at a moment in time; later entries supersede earlier ones
  where they conflict. Never edit a prior entry in place — write a new one that corrects it.
- **No secrets, no PII.** The KB is tracked in git. No API keys, no production data.
- **Add via `/kb`.** The vendored command at `.claude/commands/kb.md` is the canonical way to write
  entries (consistent shape, append-only). Manual edits are allowed for this README only.
- **`/kb` appends; you commit.** Review the diff and land it through the normal flow. To share upstream,
  copy the new entry into the project repo's `.kb/KB-storage.md`.

## When to write an entry

After a pivot, a major decision made in conversation, the end of a multi-session arc, or when a deferred
item finally lands or is dropped — state worth re-reading 6 weeks later, not a per-commit changelog.
