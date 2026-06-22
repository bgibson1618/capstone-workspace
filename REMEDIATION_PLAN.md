# Remediation Plan — post-sanity audit of Brent's slice (stores + router)

> Source: cross-source requirements-coverage audit (2026-06-21), 6 extractors (PRD / architecture /
> plan / frozen contract / our decision-log+team-notes / integration ADRs), each verified against the
> code. Triggered by the realization that "slice complete" had overlooked write-routing + Neo4j.
> The slice is solidly **built + tested in isolation** (~154 tests, stdlib-only); the gaps are the
> **write path** and **harness integration**. This file is the durable backlog; `/pickup` should treat
> it as the active priority until archived.

## ACTIVE ARC — the write path (eval-first, each its own gated PR)
Brent's directive: *"not done until the router is as accurate as we can make it on both writes and
retrievals."* Chosen sequence:
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
- **The fix (small but cross-layer):** change the write call site(s) to `self._router.write(item)` (which does
  dedup → route_write → persist), and implement `MemoryFramework.write/search` over `Router`+backends. Brent owns
  the seam (`route_write`/`Router.write` + tests, done) + an end-to-end integration test; Keith owns the plugin
  `remember()` / `MemoryFramework` call-site. **Schedule with Keith.**

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
- **Doc-honesty (TEAM_NOTES#2)** — `project-plan.md` + `stores/__init__.py` overstate ANN/Neo4j as
  shipped; mark them deferred-to-paid-path. LOW.

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
- 2026-06-21: audit run; write-path arc chosen + started.
  - Step 1 WAL: **#52 MERGED**; enforcement follow-up **#55 OPEN** (CodeRabbit — raise if a file-backed
    DB didn't get WAL).
  - Step 2 write-routing: **#56 OPEN** (D023 — `route_write`, default `base_all`; round-trip 1.000 vs
    selective 0.708; cross-vendor Codex gate PASS).
  - Step 3a dedup-on-write: **#57 OPEN** (D024 — `Router.write`, default OFF: offline lexical dedup
    can't separate near-dups from distinct-but-similar → false-merge = data loss; real-embedder-gated;
    Codex gate PASS).
  - Step 3b version-highest-wins: **DEFERRED — cross-team** (per-store vs dreaming-layer ownership, TEAM_NOTES#1).
  - **Solo write-path work COMPLETE.** Remaining is **cross-team (Keith):** `MemoryFramework` integration
    (write-routing/dedup are built but NOT LIVE — nothing calls `route_write`/`Router.write`; also
    unblocks the headline efficiency/accuracy metrics) + version-ownership.
- Archive this file once the cross-team items + the menu (benchmarks / contested labels / perf-test /
  closeout) are closed or explicitly descoped.
