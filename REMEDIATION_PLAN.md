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

## CROSS-TEAM (flag to the team; not solo)
- **Harness integration (with Keith)** — `MemoryFramework.{write,get,search,all}` are `NotImplementedError`
  stubs; the harness defaults to `InMemoryStore`. Brent's stores are **never exercised in a real run**,
  which **blocks the headline <10% efficiency + accuracy-on-vs-off metrics**. Brent owes the router/store
  side + an integration test. HIGH.
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
- **Neo4j graph backend** (uri= seam never connects; D014). NOTE: infra, *not* automatic accuracy —
  a more accurate graph needs a richer **typed/weighted edge model**, which Neo4j enables but doesn't
  provide for free. MED if pursued.
- **ANN index** (HNSW/FAISS) — brute-force cosine v1 (D013). **Reranker** (Voyage/Cohere). **bge-m3**
  air-gapped fallback. **consult-2 / RRF** (Consult2Config declared, unused). **north-star** learned
  router (D007). **17 contested labels** adjudication. **Package extraction** (ADR-eval-001; needs
  CODEOWNERS sign-off). **Persistence trust policy** (retention/TTL/encryption — ADR-P9, storage owner).

## Status
- 2026-06-21: audit run; write-path arc chosen + started. Archive this file once the arc + cross-team
  items are closed or explicitly descoped.
