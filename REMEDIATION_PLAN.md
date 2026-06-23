# Remediation Plan — post-sanity audit of Brent's slice (stores + router)

> Source: cross-source requirements-coverage audit (2026-06-21), 6 extractors (PRD / architecture /
> plan / frozen contract / our decision-log+team-notes / integration ADRs), each verified against the
> code. Triggered by the realization that "slice complete" had overlooked write-routing + Neo4j.
> The slice is solidly **built + tested in isolation** (~154 tests, stdlib-only); the gaps are the
> **write path** and **harness integration**. This file is the durable backlog; `/pickup` should treat
> it as the active priority until archived.

## WRITE-PATH ARC — ✅ COMPLETE & MERGED (was the active arc; now the live gate is the Keith integration above)
Brent's directive: *"not done until the router is as accurate as we can make it on both writes and
retrievals."* All three steps below shipped + merged (#52/#55 WAL, #56 write-routing, #57 dedup — see Status).
They are built but **NOT LIVE** until the ⭐ Keith integration (top of this file) wires them onto the write
path. Chosen sequence (historical, all done):
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
  — vectors=`memory.db`, markdown=`markdown/`, graph=in-memory (NOT persisted — the durability arc closes this).
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
    D028 captained):** a fusion profile (RRF + score-norm) ships **opt-in** via `Consult2Config`/
    `fusion_profile` (single-route stays the default). *Correction:* briefly mis-scoped as "single-best by
    design" — the router is a **speed↔accuracy spectrum**; fusion is a wanted config. **Captained verdict
    (D028, PROVISIONAL — small fixtures):** with a real embedder, vectors single-route DOMINATES (recall@5
    1.000) and fusion DILUTES it (0.900) on n=20/34-doc data; `score` > `rrf` (0.900 vs 0.850). Single-route
    is the current default. **NOT a write-off (Brent's call):** the dilution is plausibly a small-dataset
    artifact — **fusion STAYS in the comparison matrix, to be re-measured at full benchmark scale** (large
    diverse workloads where no single backend dominates may favor it). **Still open:** re-run the matrix at
    full benchmark scale (the real fusion verdict); the fusion→rerank ("accuracy+") tier; named presets; a
    recency×relevancy knob. MED.
- **Doc-honesty (TEAM_NOTES#2)** — `stores/__init__.py` overstated ANN/Neo4j as shipped → **FIXED in
  PR #64** (rewritten to v1 reality + deferred seams). `project-plan.md` may still overstate (multi-owner
  shared doc — coordinate with the team). LOW.

## CONFIRMED DEFERRALS (document; build only if the milestone requires)
- **Graph store: relational-retrieval accuracy — ✅ SHIPPED (Steps 0–semantic_seed: #75/#81/#84/#85/#86/#89,
  D029–D034); durability + delete + Neo4j are now the ACTIVE solo arc (see `GRAPH_STORE_SCOPE.md`).** The
  typed/directional edge model + multi_hop `max_depth` + accuracy-profile depth wiring + the `embed=` semantic
  seed seam all landed eval-first/in-memory. Now active (Brent 2026-06-22): graph DURABILITY (stdlib-file first)
  + DELETE (solo-additive → `[CONTRACT]`) + an e2e CRUD test across all 3 durable backends → Neo4j behind `uri=`
  (FakeBoltDriver mock + captained parity, proven a no-op on accuracy).
- **ANN index** (HNSW/FAISS) — brute-force cosine v1 (D013). **Reranker** (Voyage/Cohere). **bge-m3**
  air-gapped fallback. **consult-2 / RRF** (Consult2Config declared, unused). **north-star** learned
  router (D007). **17 contested labels** adjudication. **Package extraction** (ADR-eval-001; needs
  CODEOWNERS sign-off). **Persistence trust policy** (retention/TTL/encryption — ADR-P9, storage owner).

## Status
- 2026-06-21: audit run; write-path arc chosen + started. 2026-06-22: **all solo write-path PRs MERGED.**
  - Step 1 WAL: **#52 + #55 MERGED** (pragma + CodeRabbit enforcement — raise if a file-backed DB didn't get WAL).
  - Step 2 write-routing: **#56 MERGED** (D023 — `route_write`, default `base_all`; round-trip 1.000 vs
    selective 0.708; cross-vendor Codex gate PASS).
  - Step 3a dedup-on-write: **#57 MERGED** (D024 — `Router.write`, default OFF: offline lexical dedup
    can't separate near-dups from distinct-but-similar → false-merge = data loss; real-embedder-gated;
    Codex gate PASS).
  - Step 3b version-highest-wins: **DEFERRED — cross-team** (per-store vs dreaming-layer ownership, TEAM_NOTES#1).
  - **Solo write-path work COMPLETE + write-routing now LIVE in the eval pipeline (RouterStore #66, D025):**
    a `MemoryStore` adapter over the Router; routed writes run end-to-end through the #63 native pipeline solo
    (`WriteReceipt` proves 3-backend fan-out; Codex gate clean). Remaining is **cross-team (Keith):** adopt
    `RouterStore` at the plugin `_Engine.remember` + `MemoryFramework` stub sites (de-risked) + a captained
    large-benchmark run (real embedder) + version-highest-wins ownership.
- Archive this file once the cross-team items + the menu (benchmarks / contested labels / perf-test /
  closeout) are closed or explicitly descoped.
