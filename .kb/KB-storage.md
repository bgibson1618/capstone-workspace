# Knowledge Base — storage

**Domain owner:** Brent (P3)
**First entry:** 2026-06-22

Append-only journal of project-story snapshots for the **storage** workstream.
See [README.md](README.md) for conventions.

---

## 2026-06-22T14:11 — entry 1

**Triggered by:** manual checkpoint — first KB snapshot of the storage slice after a multi-session arc (write-path integration → reranker → fusion measurement → graph typed edges)
**Branch:** main (capstone planning repo; storage code ships from `agent-memory-harness`)
**Related ADRs:** none filed here — capstone tracks storage decisions in `DECISION_LOG.md` (D001–D029), which mirrors the project's `storage` workstream
**Note:** drafted in the capstone planning workspace, not the shared repo — sync into the project's `.kb/KB-storage.md` when sharing

### Summary
The storage slice (P3 — the three memory backends + the router) is built, measured, and largely merged; the work since the core build has been about making the router's *write* path real and pushing retrieval *accuracy* as far as honest measurement allows. Write-routing + dedup shipped behind the router (D023/D024) but were dead code until **RouterStore** (#66) — a `MemoryStore` adapter over the Router — made routed multi-index writes runnable end-to-end through the team's #63 benchmark pipeline. A **reranker** (#67) closed an audit-flagged spec gap (PRD-7). Cross-backend **fusion** (#68) was built as the accuracy end of the speed↔accuracy spectrum, then a **captained bake-off** (#72/D028) measured it with a real embedder and gave a humbling, useful result: a real semantic vectors backend *dominates* (recall 1.0) and fusion *dilutes* it on small fixtures — so single-route is the current default, but fusion stays a first-class matrix candidate to re-measure at full benchmark scale (not a write-off). Most recently the graph arc started eval-first: a link-dependent **graph-retrieval eval** (#75/D029 — itself reworked after the cross-vendor gate caught a lexical-theater first cut), then **graph Step 1** (typed/directional edges, in-flight) which flipped the eval's discrimination slices from headroom to victory.

### Key state
The router is the seam: `route(query) -> MemoryStore` (reads) + `route_write`/`Router.write` (writes; `base_all` default per D023; dedup OFF by default per D024 — offline lexical similarity can't separate near-dups from distinct-but-similar, so auto-merge = data loss). `RouterStore` (D025) is the drop-in store facade that makes both live and is the intended caller surface (`write`/`search`/`get`/`all`). The vector store is SQLite + a stdlib hashing embedder by default, real Voyage behind `embed=` (D019/D020 — the embedder is the real accuracy lever: divergence recall 0.000→1.000). The graph store is now typed + directional (relations classified from each OKF anchor via the new shared `relations.py`; maintained reverse `_in` index; query-intent traversal), with untyped links = `relates_to` generic for back-compat. Everything stays stdlib-offline by default; paid paths (Voyage embedder/reranker, eventual Neo4j) inject behind seams. The recurring discipline is the honest negative — measure before shipping a default (D022 hybrid, D024 dedup, D028 fusion).

### Open items
- **Keith integration (top cross-team gate):** the plugin / `MemoryFramework` write path doesn't call `RouterStore` yet (verified not on the remote); until wired, routed write-routing/dedup aren't live in production and the headline benchmark metrics are blocked.
- **Graph durability:** the graph backend is in-RAM, never persisted — durable graph memories need the Neo4j seam / a persistence layer (unbuilt).
- **Graph headroom remaining:** `multi_hop` (needs deeper/path-aware traversal beyond depth-2) and `semantic_seed` (needs embedder seeding) are still headroom — separate future primitives; Step 1 did typed/directional only.
- **Fusion re-measure:** the D028 verdict is provisional (small fixtures) — re-run the bake-off at full benchmark scale before any final call.
- **version-highest-wins ownership:** per-store vs dreaming-layer, unresolved cross-team (TEAM_NOTES#1).
- **Audit gap:** bge-m3 fallback embedder (PRD-6) still missing / descope-TBD.

### Artifacts at time of entry
- `DECISION_LOG.md` (D001–D029 — the storage decision record)
- `CONTEXT.md` (front door / current state)
- `REMEDIATION_PLAN.md` (backlog)
- `ROUTING_EVALS.md` (routing eval provenance)
- `GRAPH_STORE_SCOPE.md` (graph arc plan; Step 0 done)
- `STORAGE_RETRIEVAL_MAP.md` (read/write data-flow diagram)
- `docs/adrs/README.md` (local ADR-taxonomy mirror)
