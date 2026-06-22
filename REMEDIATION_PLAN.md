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

## ⭐ TOP PRIORITY (Brent's call, 2026-06-22) — WIRE WRITE-ROUTING LIVE (cross-team w/ Keith)
- **The write path bypasses the router.** Today `_Engine.remember` (`plugin/cookbook_memory/core/client.py:97-109`)
  hardcodes `self._backends["markdown"].write(...)`, and the eval `MemoryFramework.{write,get,search,all}` are
  `NotImplementedError` stubs (harness defaults to `InMemoryStore`). So **`route_write`/`Router.write`
  (write-routing #56 + dedup #57) are built but NEVER CALLED** — write-routing/dedup aren't live, AND Brent's
  stores are never exercised in a real run, which **blocks the headline <10% efficiency + accuracy-on-vs-off
  metrics**. Storage paths (for reference): backends live under `$MEMORY_STORE` (default
  `${CLAUDE_PROJECT_DIR}/.cookbook-memory`) — vectors=`memory.db`, markdown=`markdown/`, graph=in-memory.
- **✅ UPDATE (#66 / D025) — RouterStore adapter shipped (solo):** `RouterStore` (a `MemoryStore` facade over the
  Router: `write→Router.write`, `search→route().search`, `get`/`all` union+dedup) is built + eval-gated (13 tests,
  Codex gate clean), and routed writes now run **end-to-end in the #63 native eval pipeline** (`store=RouterStore`;
  `WriteReceipt` proves markdown+vectors+graph fan-out). The router seam + an integration test (Brent's) are DONE.
  **Remaining (Keith's files):** adopt `RouterStore` at the plugin `_Engine.remember` (`client.py:102`,
  markdown-hardcoded) and the `MemoryFramework.{write,get,search,all}` stubs (`framework.py:60-77`) — de-risked to
  "adopt this adapter" — plus a **captained large-benchmark metric run** (real embedder) for the headline lift
  (offline samples show parity, D019/D020 lesson). **Schedule with Keith.**

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
    (D028):** with a real embedder, vectors single-route DOMINATES (recall@5 1.000) and **fusion DILUTES it
    (0.900) — fusion loses to single-route when one backend is strong**; `score` > `rrf` (0.900 vs 0.850).
    → **The accuracy profile is real-embedder vectors single-route, NOT fusion.** Fusion is niche/opt-in
    (complementary, comparably-strong backends only). **Still open (lower priority now):** the fusion→rerank
    ("accuracy+") tier; named presets; a recency×relevancy knob — but the headline accuracy lever is wiring
    the **real embedder** (paid path), not fusion. LOW.
- **Doc-honesty (TEAM_NOTES#2)** — `stores/__init__.py` overstated ANN/Neo4j as shipped → **FIXED in
  PR #64** (rewritten to v1 reality + deferred seams). `project-plan.md` may still overstate (multi-owner
  shared doc — coordinate with the team). LOW.

## CONFIRMED DEFERRALS (document; build only if the milestone requires)
- **Graph store: Neo4j backend + relational-retrieval accuracy** — **SCOPED for next session, see
  `GRAPH_STORE_SCOPE.md`** (design-panel, 2026-06-22). Accuracy = the typed/directional edge model
  (testable in-memory, eval-first); Neo4j = infra behind the `uri=` seam, shipped last as a proven
  no-op. Ordered plan: graph-retrieval eval (Step 0) → in-memory edge model (Step 1) → embedder seeding
  → Neo4j backend (mock + captained parity). Steps 0/1 are the bankable offline win.
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
