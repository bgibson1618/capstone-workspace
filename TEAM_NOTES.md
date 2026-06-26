# Notes for the team — from Brent (2026-06-19)

Two coordination items surfaced by an independent `/sanity` review of the implemented
stores + router. Both are bigger than my slice, so I'm flagging rather than acting
unilaterally.

## 1. Version invariant: `architecture.md` says highest-version-wins, but no store enforces it

`architecture.md` (~line 49) says a store keeps the highest `MemoryItem.version` as the
current value on a conflicting write. In practice **none of the stores enforce this** — they
all do last-write-wins on `item_id`:

- `harness.InMemoryStore` (the reference), `okf.OKFStore`, and my `MarkdownStore` /
  `SqliteVectorStore` / `GraphStore`.

So either:
- **(a)** highest-version-wins is the **dreaming / persistence layer's** responsibility
  (Scott's conflict-resolution), and `architecture.md` is loosely worded → clarify the doc; or
- **(b)** the stores should enforce it → add a guard in each `write()` (skip/keep the higher
  `version` when an item already exists).

My lean is **(a)** — version conflict-resolution feels like a dreaming-worker concern, not a
per-store one — but it's a contract question for the group. Whichever we pick, let's make
`architecture.md` and the code agree and add a test. (Right now the reference store itself
violates the doc, so this isn't a one-person fix.)

## 2. `project-plan.md` overstates what shipped (production ANN / Neo4j)

> **SUPERSEDED (2026-06-23+).** The "graph deferred / in-memory untyped, real-paid path behind
> injection seams" framing below is now **STALE for the graph backend**. Since this note: the graph
> shipped **typed/directional edges** (#81/D030), **durability** via the `path=` SQLite seam
> (#92/D035), and the **Neo4j Phase-A parity floor merged** (PR **#111, D041**, Bolt transport per
> D039) — so the graph is now typed/directional **and** durable, and the live plugin builds it with
> `path=` (`contract.py:100` → `GraphStore(path=…/graph.db)`). Authoritative current state =
> `CONTEXT.md` + `GRAPH_STORE_SCOPE.md` (Neo4j Phase-B is the only graph thread still parked, gated
> on the captained live `NEO4J_TEST_URI` run). The original note is kept below as a historical record.

`project-plan.md` (~line 181) reads as if the production pieces — SQLite + a real embedding
model + HNSW/FAISS, and a Neo4j typed-traversal graph — were delivered for my slice. What
actually shipped is honest **stdlib v1**: char-n-gram hashing + brute-force cosine, and an
in-memory untyped link graph, with the real/paid path deferred behind injection seams
(`embed=`, `uri=`). This is intentional and documented on my side (DECISION_LOG D013/D014),
but the plan doc should say *"v1 stdlib offline shipped; production embeddings / Neo4j deferred
to the paid path"* so our status is accurate — especially for how we describe the project
externally.

## 3. Pipeline SUMMARY "Memory health" under-reports `recall_events` (cc @kenhuangus @kmazanec) — 2026-06-26

The `make pipeline` SUMMARY (`.md` + `.json`) carries **two recall counters that disagree** for a
memory-on stage. On the xarray `plugin-accum` run @ `72d00a7` (banked, PR #196):

- **Stage-level** (the truth): `recall_attempted = 22`, `recall_with_hits = 22`, `memory_reached = 22`,
  `memory_hit = 22` — memory was recalled AND hit on all 22 tasks.
- **`memory_health.*` block** (what the SUMMARY "Memory health" TABLE prints): `recall_events = 0`,
  `recall_with_hits = 0`, `recall_zero_hits = 0`.

So the human-facing scoreboard table shows **memory as completely unused** (`recall events 0`) when the
stage-level counters prove it was used every task. The contrast is clean: the no-memory `builtin` stage
has BOTH sets at 0 (correct), so it's specifically the `memory_health` aggregation that's broken for a
memory-on stage — it isn't reading the same recall events the stage-level counters do (possibly it reads
the accum store's own event log, which the seeded/copied store path leaves empty, vs the live per-task
recall instrumentation).

**Impact:** anyone reading the SUMMARY table would conclude "memory did nothing," masking the actual
+1-task lift. **Ask:** point the `memory_health.recall_events`/`recall_with_hits` aggregation at the same
source as the stage-level `recall_attempted`/`recall_with_hits` (or document which is canonical). This is
eval-harness / reporting (Ken/Keith's domain), not a stores/router bug — flagging, not acting
unilaterally. Repro data: `results/vpydata_xarray_sequence-plugin-accum-72d00a7-1/SUMMARY-*.json`
(`stages[0].recall_attempted` vs `stages[0].memory_health.recall_events`).
