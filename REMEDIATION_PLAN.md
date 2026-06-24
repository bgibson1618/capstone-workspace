# Remediation Plan — post-sanity audit of Brent's slice (stores + router)

> Source: cross-source requirements-coverage audit (2026-06-21), 6 extractors (PRD / architecture /
> plan / frozen contract / our decision-log+team-notes / integration ADRs), each verified against the
> code. Triggered by the realization that "slice complete" had overlooked write-routing + Neo4j.
> The slice is solidly **built + tested in isolation** (stdlib-only; stores suite now **337 passed / 3 skipped (340 collected)**). *As originally audited (2026-06-21)* the gaps were the
> **write path** and **harness integration** — both since SHIPPED (write-path LIVE via RouterStore #76; durability hardening #117 MERGED). The current active priority is the **captained large-benchmark
> metric run** (the headline gate) + the deferred hardening / Neo4j follow-ups below. This file remains the durable backlog.

## 🛠 BACKEND DURABILITY HARDENING ARC — ✅ DONE & MERGED (PR #117, D042, 2026-06-23, squash `9d77ecb`)
> Source: the `store-durability-audit` Workflow (2026-06-23, 52 agents, adversarially verified + empirically
> crash-tested). **Full findings: `BACKEND_DURABILITY_AUDIT.md`. Decision: `DECISION_LOG.md` D040** (+ D039 Bolt) → **arc shipped as D042.**
> **Original verdict: both durable backends `needs-hardening`; markdown/OKF effectively POC persistence.** Both LIVE on
> the product path (every `remember` fans out to all backends; Daydreamer writes the same dir cross-process). Built
> eval-first immediately after the graph thread shipped (D041), per Brent's circle-back call.
>
> **✅ SHIPPED & MERGED (PR #117 `stores/backend-durability-hardening`, squash `9d77ecb`; gate journey: cross-vendor
> Codex R1 FAIL → R2 FAIL → R3 PASS — each round caught a real cross-process WRITE-coherence bug, refresh-seam-incomplete
> → mtime-race → writer-side generation-stale-ack — then a CodeRabbit fold of 6 quick-wins). Instrument: `test_backend_durability.py`
> (16 tests). Gates: durability 16/16; full stores `discover` 337 passed / 3 skipped (340 collected); smoke 95 passed / 1 skipped (96 collected). No `[CONTRACT]` change:**
> 1. **markdown/OKF HIGH-1 — atomic write: DONE** (`tmp.replace`+fsync, **per-call temp** — torn update no longer loses prior data).
> 2. **markdown/OKF HIGH-2 — cross-process lock + read-refresh: DONE** (`flock` + a **persisted generation-counter** with
>    **reconcile-under-lock on write/delete/flush** — read-your-peers'-writes coherence — + a read-refresh seam; the mtime
>    approach was tried and rejected at gate R2 because mtime granularity can't detect a same-tick peer write).
> 3. **markdown/OKF HIGH-3 — delete fast-path: DONE** (O(1) `unlink` of the known relpath; rglob only for foreign filenames).
> 4. **sqlite — thread-safe connection: DONE** (serialized under the lock — the harness's `run_agent(workers>1)` path).
> 5. **sqlite — `write()` rollback + `close()`/lifecycle under the lock: DONE.** **graph — thread-safe `path=` mirror: DONE.**
> 6. **markdown/OKF MED tail — autoload corrupt-file guard: DONE** (catches parse/convert errors). **Still deferred** (below).
>
> **🔭 DEFERRED hardening follow-ups (out of #117's scope — tracked, queued; D042):**
> - **GraphStore cross-process READ freshness** — the SAME generation-counter coherence class the markdown store now has; a
>   **pre-existing residual, NOT a regression** this arc introduced (the graph `path=` mirror is thread-safe but not yet
>   cross-process-fresh). Apply the same persisted-generation-counter pattern when revisited.
> - **markdown MEDs:** slug-collision hash-suffix (`okf.py:277-280`); type-change orphan-resurrection unlink-on-write
>   (`okf.py:396-400`); persisted/lazy inverted index (eager-load/duplicate-postings).
> - **sqlite MED/LOW perf:** score on `(id, vector)` tuples, materialize only k survivors (`sqlite_store.py`) — a pre-ANN
>   constant-factor win (the real scaling fix is the deferred D013 ANN swap).

## WRITE-PATH ARC — ✅ COMPLETE & MERGED (RouterStore now adopted on the live plugin path, #76; the remaining live gate is the captained benchmark run — see the ⭐ section above)
Brent's directive: *"not done until the router is as accurate as we can make it on both writes and
retrievals."* All three steps below shipped + merged (#52/#55 WAL, #56 write-routing, #57 dedup — see Status).
They are now **LIVE on the product path** — the plugin consumes them via `RouterStore` / `contract.build_store`
(#76, ADR-harness-011; see the ⭐ section below). Chosen sequence (historical, all done):
1. **WAL quick-win** — `SqliteVectorStore` opens sqlite with no `PRAGMA journal_mode=WAL` (ADR-P2: WAL
   mandatory). Concurrency hazard once MCP writes + the Daydreamer share one `$MEMORY_STORE` file.
   Fully owned, ~1 line + a file-backed test. *(verified: sqlite_store.py connect, no pragma)*
2. **Write-routing** — add `Router.route_write(item) → backend(s)` (classify memory CONTENT, not just
   queries); route `remember`/daydream writes through it. Eval-first: a **write→retrieve round-trip**
   eval (write a routed memory, then query for it, does it come back?) + classify-on-declarative-content
   coverage. *(verified: router is read-only; writes hardcode markdown; MemoryFramework.write is a stub)*
3. **Dedup-on-write + version-highest-wins** — similarity-merge → bump version, return id (ADR-P2/P4,
   an explicit storage/Brent open question); enforce highest-version-wins so a stale lower-version write
   can't clobber. *(verified: all stores INSERT-OR-REPLACE / last-write-wins; version inert)*

## ⭐ TOP PRIORITY (UPDATED 2026-06-22) — WRITE-ROUTING IS NOW LIVE; remaining = the captained benchmark run
- **✅ The write path now routes through the router (#76 / ADR-harness-011, verified in code).** The plugin was
  refactored to a **dumb client of `contract.build_store`**, which returns a **`RouterStore` over
  `Router.with_config(...)`**: `_Engine.remember` → `store.write` (routed + deduped; the old
  `self._backends["markdown"].write(...)` hardcode is GONE), `recall` → `store.search`, and the engine
  **auto-selects the profile** (`$MEMORY_PROFILE` / `VOYAGE_API_KEY`→accuracy / else fusion). Dreaming routes
  through the same seam (#79). So **`route_write`/`Router.write` (write-routing #56 + dedup #57) are now CALLED on
  the product path** — the "writes bypass the router / stores never exercised" framing that drove this section is
  **obsolete.** Storage paths (reference): under `$MEMORY_STORE` (default `${CLAUDE_PROJECT_DIR}/.cookbook-memory`)
  — vectors=`memory.db`, markdown=`markdown/`, graph=`graph.db` (NOW persisted — Keith wired `contract.py:100` to
  `GraphStore(path=…/graph.db)` this session; the durability arc + this wiring closed the gap, verified end-to-end).
- **✅ RouterStore adapter (#66 / D025, solo):** the `MemoryStore` facade over the Router (`write→Router.write`,
  `search→route().search`, `get`/`all` union+dedup), eval-gated (13 tests, Codex clean) — exactly what the plugin
  adopted in #76.
- **What actually remains:** (a) a **captained large-benchmark metric run** (real embedder; now auto-accuracy-profile
  with the key) for the headline <10%-overhead + accuracy-on-vs-off lift over `InMemoryStore` (offline samples show
  parity, D019/D020 lesson) — **the real headline gate**; (b) the eval-harness `MemoryFramework.{write,get,search,all}`
  stubs (`framework.py:60-77`) are still `NotImplementedError` but the live plugin/bench path BYPASSES them (uses
  `build_store`) → a decide-wire-or-retire, not a blocker; (c) version-highest-wins ownership (cross-team).

## CROSS-TEAM (flag to the team; not solo)
- **`version` invariant ownership** — per-store vs dreaming/persistence layer (TEAM_NOTES#1). Decide, then
  make architecture.md + code agree.
- **Recall-only surface** — legacy `claudecode/memory_server.py` still registers `memory_remember`,
  violating ADR-harness-008 (recall-only, contract:true). Keith's surface; backs Brent's stores. MED.

## FULLY-OWNED, OVERLOOKED (not write-routing/Neo4j)
- **Backend performance testing** — explicit P3 deliverable (project-plan §5: "performance-test each
  backend"); zero code (per-backend write+search latency/throughput at scale). MED.
- **Cross-store consistency** — markdown mutates the caller's `item` on write; sqlite/graph don't.
  Decide one rule in the protocol docstring + a shared conformance test. MED.
- **Test-parity gaps** — as_of-at-equality (only sqlite), markdown `all()` untested, k=0/negative (only
  graph), graph full-field round-trip. LOW (code correct; removes silent-regression exposure).
- **Commit live results as artifacts** — D020 (recall@5 0→1.0) + D021 bake-off live numbers live only in
  throwaway `work/` scripts; commit a captioned results artifact for reproducible evidence. LOW.
- **Audit-flagged spec gaps (#61 PRD-compliance, surfaced via the pickup impact scan):**
  - **Reranker (PRD-7)** — ✅ **DONE (#67, D026):** `stores/rerankers.py` (`MockReranker` + `VoyageReranker` +
    `rerank_items` + `RerankedStore` over top-N; composes with `RouterStore`). Offline = mechanism only; the
    quality lift is a captained run, and wiring it onto the default retrieval path is a follow-up.
  - **bge-m3 fallback embedder (PRD-6)** — still missing (an air-gapped open-source embedder behind the `embed=`
    seam; only Voyage + the hashing/Mock default ship). LOW — descope-or-build TBD.
  - **Cross-backend fusion / read-orchestrator (PLAN-7)** — ✅ **DONE + MEASURED (#68 D027, #72 bake-off,
    D028 captained):** a fusion profile (RRF + score-norm) ships via `Consult2Config`/
    `fusion_profile`, and the engine **auto-selects fusion as the offline default** (`VOYAGE_API_KEY`→accuracy
    / else **fusion** — see ~lines 55–65 + ADR-storage-003); single-route is an explicit profile, not the
    default. *Correction:* briefly mis-scoped as "single-best by
    design" — the router is a **speed↔accuracy spectrum**; fusion is a wanted config. **Captained verdict
    (D028, PROVISIONAL — small fixtures):** with a real embedder, vectors single-route DOMINATES (recall@5
    1.000) and fusion DILUTES it (0.900) on n=20/34-doc data; `score` > `rrf` (0.900 vs 0.850). Single-route
    **DOMINATED at these small D028 fixtures**, but **fusion is the shipped offline default** and a
    re-measure-at-scale candidate — not a verdict to make single-route "the default." **NOT a write-off
    (Brent's call):** the dilution is plausibly a small-dataset
    artifact — **fusion STAYS in the comparison matrix, to be re-measured at full benchmark scale** (large
    diverse workloads where no single backend dominates may favor it). **Still open:** re-run the matrix at
    full benchmark scale (the real fusion verdict); the fusion→rerank ("accuracy+") tier; named presets; a
    recency×relevancy knob. MED.
- **Doc-honesty (TEAM_NOTES#2)** — `stores/__init__.py` overstated ANN/Neo4j as shipped → **FIXED in
  PR #64** (rewritten to v1 reality + deferred seams). `project-plan.md` may still overstate (multi-owner
  shared doc — coordinate with the team). LOW.

## CONFIRMED DEFERRALS (document; build only if the milestone requires)
- **Graph store: relational-retrieval accuracy + durability + delete — ✅ SHIPPED & MERGED (#75/#81/#84/#85/#86/#89
  accuracy + #92 durability + #93 delete + #95 e2e CRUD + #99/#101 delete-`[CONTRACT]`; D029–D038; see
  `GRAPH_STORE_SCOPE.md`).** The typed/directional edge model + multi_hop `max_depth` + accuracy-profile depth +
  the `embed=` semantic-seed seam + a `path=` SQLite durability seam + delete across all backends + an e2e CRUD
  test (survives restart) + `delete` on the `MemoryStore` protocol all landed eval-first + gated. **Neo4j Phase-A
  parity floor — ✅ SHIPPED (PR #111, D041; Bolt per D039):** `Neo4jGraphStore` behind `uri=` reproduces the
  in-memory id-set+order exactly (FakeBoltDriver mock + opt-in `NEO4J_TEST_URI` live test). **The whole solo graph
  thread is now DONE.** Remaining graph follow-up: **Neo4j Phase B** (native typed graph, D043, PARKED — gated on
  the captained live `NEO4J_TEST_URI` run). The cross-team plugin `build_store` graph-path wiring (Keith) is **✅ DONE
  this session** (`contract.py:100` → `GraphStore(path=…/graph.db)`; the LIVE plugin graph is now durable, verified end-to-end).
- **ANN index** (HNSW/FAISS) — brute-force cosine v1 (D013). **Reranker** (Voyage/Cohere). **bge-m3**
  air-gapped fallback. **consult-2 / RRF** (Consult2Config declared, unused). **north-star** learned
  router (D007). **17 contested labels** adjudication. **Package extraction** (ADR-eval-001; needs
  CODEOWNERS sign-off). **Persistence trust policy** (retention/TTL/encryption — ADR-P9, storage owner).
- **Neo4j Phase B** (D043, PARKED) — a `native=True` mode INSIDE `Neo4jGraphStore`: materialize the native
  `[:REL]` graph from the persisted `okf_links` SSOT (**`MATCH` endpoints, never `MERGE`** — the D041 R1 bug),
  native Cypher/GDS search; the transient-delegation path stays the default + regression baseline. **HARD
  prereq = the captained live `NEO4J_TEST_URI` run.** Scoped in `GRAPH_STORE_SCOPE.md`.
- **FalkorDB-as-a-backend — REOPENED as a candidate (D044), pending eval-first measurement.** Design risks to
  engineer around (stdlib stays the offline test floor): the draft
  `FalkorGraphStore` re-introduced D041's fixed placeholder + seq bugs (must `MATCH`-never-`MERGE`); `falkordblite` is a managed
  **subprocess** (not in-process), Python 3.12+/Linux-macOS/libomp (NOT zero-dep stdlib). Research:
  `docs/falkordb_comparison.md`, `docs/local_stores_performance.md` (both verified PARTIAL).

## Status
- 2026-06-21: audit run; write-path arc chosen + started. 2026-06-22: **all solo write-path PRs MERGED.**
  - Step 1 WAL: **#52 + #55 MERGED** (pragma + CodeRabbit enforcement — raise if a file-backed DB didn't get WAL).
  - Step 2 write-routing: **#56 MERGED** (D023 — `route_write`, default `base_all`; round-trip 1.000 vs
    selective 0.708; cross-vendor Codex gate PASS).
  - Step 3a dedup-on-write: **#57 MERGED** (D024 — `Router.write`, default OFF: offline lexical dedup
    can't separate near-dups from distinct-but-similar → false-merge = data loss; real-embedder-gated;
    Codex gate PASS).
  - Step 3b version-highest-wins: **DEFERRED — cross-team** (per-store vs dreaming-layer ownership, TEAM_NOTES#1).
  - **Solo write-path work COMPLETE; RouterStore (#66, D025) ADOPTED on the live plugin path (#76/ADR-harness-011):**
    `contract.build_store` returns a `RouterStore`, so `_Engine.remember` routes writes (dedup + base_all fan-out)
    and dreaming routes through it too (#79). `MemoryFramework` stays a stub, but the live plugin/bench path
    bypasses it (uses `build_store`).
  - **Graph arc COMPLETE & MERGED (2026-06-23):** semantic_seed (#89/D034) + durability `path=` SQLite seam
    (#92/D035) + delete across all backends (#93/D036) + e2e CRUD across all 3 durable backends (#95/D037) +
    `delete` on the `MemoryStore` protocol (#99 + #101/D038).
  - **Remaining:** a **captained large-benchmark run** (real embedder — the headline metrics gate) +
    version-highest-wins ownership + MemoryFramework wire-or-retire. *(The cross-team plugin `build_store`
    graph-path wiring — Keith — landed 2026-06-23: `contract.py:100` → `GraphStore(path=…/graph.db)`; LIVE plugin
    graph now durable, verified end-to-end.)*
- **2026-06-23: backend durability audit run** (`store-durability-audit` Workflow) → **Backend Durability
  Hardening Arc** added at the top. Both durable backends `needs-hardening`; markdown/OKF effectively POC
  persistence. Full findings: `BACKEND_DURABILITY_AUDIT.md`; decisions D039 (Bolt) + D040 (audit/arc).
- **2026-06-23: Neo4j Phase-A parity floor — DONE (PR #111, D041)** — the last solo graph thread. The
  durability arc became now-next, and shipped same-session.
- **2026-06-23: Backend Durability Hardening Arc — DONE & MERGED (PR #117, D042, squash `9d77ecb`).**
  markdown/OKF made production-durable (atomic write + cross-process flock + persisted generation-counter
  w/ reconcile-under-lock + O(1) delete + corrupt-file guard); sqlite/graph thread-safe. Gate: Codex
  R1 FAIL→R2 FAIL→R3 PASS + CodeRabbit fold. `test_backend_durability.py` (16); durability 16/16, stores
  337 passed / 3 skipped (340 collected), smoke 95 passed / 1 skipped (96 collected). **Deferred follow-ups recorded** (GraphStore cross-process read freshness —
  a pre-existing residual, not a regression — + markdown MEDs).
- **2026-06-23: research + architecture-reconcile Workflow — DONE (D043).** `docs/falkordb_comparison.md`
  + `docs/local_stores_performance.md` verified (both PARTIAL — Falkor draft re-introduced D041's fixed bugs
  (design risk: MATCH-never-MERGE) — FalkorDB REOPENED D044 as a candidate graph backend pending eval (stdlib
  stays the test floor); FTS5-cache doesn't fix durability, validating the D042
  direction). 8 backend-arch drifts → 7 storage ADRs (ADR-storage-003..009, **PR #118 MERGED, squash `6b03d32`**).
  architecture.md reconciled on LOCAL `docs/architecture-reconcile` (01562b3, UNPUSHED — `[CONTRACT]`, a
  team-meeting governance call). Neo4j **Phase-B plan drafted + PARKED** (gated on the captained live run).
- **Open now (Brent / captained / team):** (1) #117 + #118 **MERGED** (squash `9d77ecb` / `6b03d32`); (2) the deferred hardening
  follow-ups; (3) the **captained live `NEO4J_TEST_URI` run** (Cypher validity; HARD prereq for Phase B);
  (4) **Neo4j Phase B**; (5) architecture.md reconciliation → team meeting → push/merge. **⭐ Headline gate:
  the captained large-benchmark run.** *(Keith's plugin `build_store` graph-path wiring is DONE — `contract.py:100`;
  the live plugin graph is durable. The only remaining graph-durability item is the captained live `NEO4J_TEST_URI` run.)*
- Archive this file once the cross-team items + the deferred hardening follow-ups + Neo4j Phase B + the menu
  (benchmarks / contested labels / perf-test / closeout) are closed or explicitly descoped.
