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

## 3. Pipeline SUMMARY "Memory health" table: the `recall events`/`hit events` columns under-report on a seeded stage (cc @kenhuangus @kmazanec) — 2026-06-26

**Symptom.** The "Memory health" table's `recall events` + `hit events` columns read **0** for the seeded
`plugin-accum` stage even though memory was recalled on every task. The table has TWO recall sources side
by side, and they're not the same unit and don't agree:

| run | `recall tasks` / (hit) — trajectory, PER-TASK | `recall events` / `hit events` — event-log DELTA |
|---|---|---|
| `plugin-blank` (non-seeded) | 21 / 14 | 11 / 7 |
| `plugin-accum` (**seeded**) | 22 / 22 | **0 / 0** |

(The no-memory `builtin` stage is 0 on both, correctly.)

**Root cause (traced in code).**
- The **`recall tasks` column** = `stage.recall_attempted` (`eval/memeval/agent.py:417`), a PER-TASK count
  of trajectories that did a `retrieve` step. **This is the reliable signal** and is correct (22).
- The **`recall events` / `hit events` columns** = `memory_health.delta.recall_events` /
  `recall_with_hits` (`pipeline_summary.py:305`), a DELTA of `"recall"` op-records in the run's
  `_memory/.cookbook-memory/events.jsonl` (`pipeline.py:738-761`, `_store_health`), taken as
  `after − before` around the stage (`pipeline.py:1331/1336`).
- On a **seeded** stage, the store is `copytree`'d from the source (`pipeline.py:788 _copy_memory_dataset`),
  so `events.jsonl` **already contains the seed's 11 `recall` records** (all `ts: 0.0`) at the `before`
  snapshot. The accum run then appended 260 `note` + 54 `daydream` records but **0 new `recall` records**,
  so `after.recall_events == before.recall_events == 11` → **delta 0**.
- Even on the NON-seeded `plugin-blank` the two disagree (11 logged vs 21 tasks recalled) — so the
  events.jsonl `recall`-op logging is **incomplete** generally, not just on seeded runs; seeding merely
  drives the delta to 0.

**Two real issues:** (a) the events.jsonl `recall`-op logging doesn't capture all task-time recalls
(11 logged vs 21 tasks), and (b) the table presents that unreliable delta as a headline column next to the
correct per-task one — so a seeded run reads as "recall events 0," masking the lift.

**Fix — recommended (worked out):**
1. **Reporting (low-risk, `eval/memeval/claudecode/pipeline_summary.py:298,304-305`):** make the table's
   recall columns the authoritative PER-TASK trajectory counters. Concretely: keep `recall tasks`
   (`recall_attempted`); ADD a `hit tasks` column from `s.get('recall_with_hits')` (already in the stage
   dict, currently unused in the table); and DROP the `mh.recall_events` / `mh.recall_with_hits` columns
   from the .md table (leave them in the detailed JSON for observability). This makes the scoreboard
   consistent across builtin / blank / seeded with no behavior change to the run.
2. **Root cause (harness/plugin, Keith/Ken):** if `events.jsonl` is meant to be authoritative recall
   observability, the plugin's recall path should append a `"recall"` op for EVERY task-time recall (it
   currently logs ~half), and the seed's copied recall records should be excluded from the `before`
   baseline (or the seed's `ts:0.0` records dropped on copy) so a seeded delta isn't structurally zeroed.

This is eval-harness / reporting (Ken/Keith's domain), not a stores/router bug — flagging with a concrete
fix, not acting unilaterally. Repro: `results/vpydata_xarray_sequence-{plugin-blank-6a0b0b4-3,plugin-accum-72d00a7-1}/SUMMARY-*.json`
(`stages[0].recall_attempted` vs `stages[0].memory_health.recall_events`).
