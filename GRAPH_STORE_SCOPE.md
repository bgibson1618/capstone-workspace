# Graph Store — scope for next session (Neo4j + relational-retrieval accuracy)

> Scoped 2026-06-22 via a blind design-panel (4 angles, unanimous on the core call), grounded in the
> actual code. This is the working plan to start the graph-store thread next session. Eval-first, same
> discipline as D008/D019–D024. Brent sets final direction; adjust before building.

> **STATUS: Graph Steps 0 (#75/D029), 1 (#81/D030), 1b (#84/D031) DONE.** Step 0 = `test_graph_retrieval_evals.py` — the graph-retrieval
> eval ships as a **link-dependent headroom instrument**: a coined-token corpus + a link-stripped
> DIFFERENTIAL (every case must behave differently with vs without links, 8/8) — after a first cut was
> caught by the cross-vendor gate as lexical theater (stripping links changed nothing). 4 slices
> (typed_direction / relation_disambiguation / multi_hop / untyped_fallback control); semantic_seed
> deferred to the embedder-seed step. **Steps 1 (#81/D030) + 1b (#84/D031) now DONE** — typed/directional
> edges + `okf.py` anchor-capture (real OKF `[depends on](x.md)` links typed end-to-end, always-tuple
> `okf_links`; gated by `test_okf_to_graph.py`, 9 tests). **multi_hop also DONE (#85/D032 = configurable
> `max_depth`, a knob that recovers the depth-3 gold; default byte-equiv).** **accuracy-profile wiring DONE
> (#86/D033 — cascade injects per-query depth, accuracy=3 PROVISIONAL).** **semantic_seed DONE (#89/D034 —
> `embed=` hybrid cosine seam, mechanism-only; byte-equiv offline; captained accuracy deferred).**
>
> **NEXT ARC (Brent 2026-06-22): durable graph → e2e CRUD across all 3 backends.** Durability ≠ Neo4j —
> stdlib-first gets a real CI-runnable e2e *now*; Neo4j follows as the real-DB step. Ordered, each eval-first
> + gated: (1) **Graph DURABILITY — ✅ DONE & MERGED (#92/D035, 4-round gate R4-PASS):** stdlib `path=` SQLite seam
> (`$MEMORY_STORE/graph.db`; persist nodes, rebuild `_out`/`_in` on load from `okf_links` = single source of
> truth; `path=None` byte-equiv; recompute embeddings on load; **atomic** write parse→embed→persist→index +
> `_persist` rollback; `close()`/post-close fail-loud). (2) **DELETE — ✅ DONE (#93/D036, OPEN; internal-gate 0 +
> Codex R1/R2 PASS):** solo-additive/duck-typed `delete(item_id)` on the 3 backends (durable; graph atomic +
> mirror-preserving) + `Router`/`RouterStore` fan-out (idempotent); **PLUS the `[CONTRACT]` PR (#99/D038,
> 4-owner, Codex R1→R4 PASS) that promotes `delete` to the frozen `MemoryStore` protocol** — DONE. (3) **E2E CRUD — ✅ DONE (#95/D037, OPEN; Codex R1→fold→R2 PASS):**
> a real RouterStore over all 3 durable backends — Create→Read→Update→Delete→restart-from-disk→confirm, per-backend
> + anti-theater. **The durability→delete→e2e arc is COMPLETE.** (4) **Neo4j behind `uri=` — remaining follow-up:**
> FakeBoltDriver mock (Cypher/`as_of`/`LIMIT`) + a captained id-set/order parity run (proven a no-op on accuracy).
> Plus: the `[CONTRACT]` delete-on-protocol PR (4 owners) and the cross-team plugin `build_store` graph-path
> wiring (Keith — makes the LIVE plugin graph durable).**

## The core call (panel unanimous)
**Relational-retrieval ACCURACY lives in the edge model + traversal — fully testable in-memory,
zero-dependency. Neo4j is INFRASTRUCTURE, not accuracy; it ships LAST and its only job is to reproduce
the in-memory numbers (proven a no-op on accuracy), not improve them.** Building Neo4j first spends the
hardest engineering on the part that moves no metric and asks reviewers to trust a DB they can't run in
CI — inverting the eval-first ethos. (REMEDIATION_PLAN already says "Neo4j is infra, not automatic accuracy.")

## Starting state (the v1 store this plan began from — NOW SUPERSEDED)
> ⚠️ **Historical.** The paragraph below describes the PRE-plan v1 store, kept for the plan's rationale. It
> is **no longer current** — see the STATUS block at the top: Steps 1/1b made edges **typed + directional**
> (`relations.py` + `okf.py` anchor capture), #92 added the **`path=` SQLite durability seam**, #93/#99/#101
> added **`delete`** (now on the `MemoryStore` protocol), and the graph-retrieval eval shipped at Step 0 (#75).
>
In-memory stdlib `graph_store.py`: nodes=memories; `metadata["okf_links"]`=edges, **untyped + undirected**
(every edge runs both ways); search = seed by query-token Jaccard → undirected BFS depth 2, score
`seed_overlap * 0.5**hops` → top-k; `as_of` honored; link targets resolved by a basename heuristic
(`_link_id`, assumes id==slug); `_neighbors` does an O(V*E) in-edge scan; `uri=` Neo4j seam exists but is
**never used**. No graph-retrieval eval exists.

## Three failure modes to attack (each pinned to source) — ALL now addressed (see STATUS)
1. **Silent edge mis-resolution** — `graph_store.py:51-59` `_link_id` basename heuristic → on a referential
   Neo4j backend this becomes dropped/wrong edges. Fix: resolve targets via `x_item_id` (`okf.py:48,203,226`)
   reusing the router's `_identity_index`/`_norm_identity` (`router.py:537-565`) — the same resolver the D008
   cascade gate already trusts. Reuse; don't reinvent.
2. **Untyped+undirected answers directional questions wrong** — "what breaks if I change X" (in-edges) is
   indistinguishable from "what does X depend on" (out-edges). The measurable accuracy gap.
3. **Self-confirming eval** — zero graph eval today; building the edge model without one repeats the D008-PR1 trap.

## Where relation types come from (the cheap, verified win)
OKF links carry no type today **because the parser throws it away**: `okf.py:55`
`_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")` captures only the target and discards the `[...]` anchor
text — which is exactly where the relation lives ("depends on", "calls", "conflicts with").
- **Extract the type at OKF-parse time** (capture the anchor), NOT from the router's query regexes (those
  classify queries, not edges).
- **Share one vocabulary:** a single `classify_relation(anchor_text) -> str` over a closed enum, built from
  the router's `_GRAPH_RE` terms (`router.py:54-59`: depends-on/calls/uses/imports/conflicts/contradicts/
  renames/impacts), imported by BOTH the extractor and the router. One taxonomy, one source of truth.
- **Default `relates_to`** when no relation verb is present (most existing links are plain text → low typed
  coverage). `relates_to` traverses **both directions** so the offline default never regresses when labels
  are absent. Weight typed edges (1.0) above the `relates_to` fallback.

## In-memory edge model + traversal (Step 1 — the bankable win)
- `self._out: dict[id -> list[Edge]]` where `Edge` is a stdlib `@dataclass(slots=True, frozen=True)`
  `(target_id, rel_type, weight, direction)`.
- Maintain a reverse-adjacency `self._in` index at `write()` — kills the O(V*E) scan AND makes directional
  traversal trivial (OUT=`_out`, IN=`_in`, BOTH=union).
- Module-top `_TRAVERSAL = {rel: Direction}` table: depends_on/calls/imports → OUT; impact/"what breaks" → IN;
  conflicts_with/relates_to → symmetric. Decay by edge weight, not flat `0.5**hops`.

## Semantic seeding behind `embed=` (Steps 2–3)
Swap token-Jaccard seeding for cosine seeding behind the SAME `embed=` seam SqliteVectorStore +
SemanticRouterClassifier use; default `None` → today's Jaccard (offline stays zero-dep). Reuse the
`input_type` helper. **Offline can only prove HEADROOM** (lexical path misses → real encoder recovers); the
real accuracy win is **captained-only** (D019/D020 lesson). Sequence below the CI-provable typed-edge work.

## Neo4j behind `uri=` (Steps 4–5) — proven a no-op
- `Neo4jGraphStore` behind the unused `uri=`; `import neo4j` **lazily inside `connect()` only** (VoyageEmbedder
  discipline); in-memory stays the offline default.
- **Fail LOUD** on a set `uri` with no driver (mirror VoyageEmbedder's missing-key RuntimeError) — never
  silently fall back and mislabel the run.
- Both backends share ONE traversal/scoring contract (same `Edge`, `_TRAVERSAL`, seed→traverse→score), so the
  eval is backend-agnostic and Neo4j is provably no-op on accuracy.
- **Test without a server:** committed `FakeBoltDriver`/`FakeSession` stdlib mock (the `MockEmbedder` +
  monkeypatched-`urlopen`-with-canned-JSON pattern from `test_embedders.py`) asserting emitted Cypher
  MERGE/MATCH shape, the `as_of` bound, and `LIMIT k`. Plus ONE captained live run in gitignored `work/`
  (per `voyage_live_eval.py`, Brent-authorized) replaying the committed eval against real Neo4j.
- **Parity = id-set/order, NOT float scores** — force the in-memory tie-break tuple `(-score, -relevancy,
  -timestamp, item_id)` (`graph_store.py:128`); Cypher vs Python float ordering can diverge.

## Ordered build plan (each its own eval-first, gated PR)
> **Step 1 — ✅ DONE (#81, D030):** typed/directional edge model (`relations.py` + `graph_store.py` reverse `_in` index + intent-driven traversal); the eval's discrimination slices flipped headroom→victory; back-compat via untyped=`relates_to`-generic. `query_intent` direction is a recall-safe best-effort heuristic (7 cross-vendor gate iterations). **Step 1b — ✅ DONE (#84, D031):** `okf.py` `_LINK_RE` now captures the link anchor and `doc_to_memory_item` emits `okf_links` as `(anchor, target)` tuples (always-tuple — `okf.py` stays a pure parser, no `stores/` import; the store classifies the anchor), so real OKF links are typed end-to-end. Gated by `test_okf_to_graph.py` (9 tests, parses real OKF markdown; link-stripped anti-theater differential; RED→GREEN). **multi_hop — ✅ DONE (#85, D032):** configurable `GraphStore(max_depth=)` (default `_MAX_DEPTH`, byte-equiv); the eval's deep-config slice flips headroom→victory (`max_depth=3` recovers the depth-3 gold, links-only). Mechanism+eval only. **Accuracy-profile wiring — ✅ DONE (#86, D033):** the cascade injects per-query `max_depth` into its graph stage; `accuracy_profile(graph_max_depth=3)` (PROVISIONAL — captained "does deeper help" deferred). **Then:** embedder seeding (semantic_seed — IN PROGRESS), Neo4j durability.

0. **Instrument first — ✅ DONE (#75, D029).** `test_graph_retrieval_evals.py`, cloning the D008/D020 template (Case dataclass,
   slices, machine-asserted invariants, **blind multi-lens authorship → deterministic calibration** dropping
   floor-solved cases). Slices: `typed_direction`, `multi_hop`, `relation_disambiguation`, `untyped_fallback`
   (control), `semantic_seed` (headroom). Anti-theater: today's untyped/undirected graph MUST miss the
   directional/multi-hop gold. No store change, no accuracy claim until this exists.
1. **Edge model + reverse index** (in-memory, zero-dep): Edge dataclass; `_in`; `_TRAVERSAL`;
   `classify_relation` over shared `_GRAPH_RE`; capture OKF anchor (`_LINK_RE`); resolve via `_identity_index`/
   `x_item_id`. Turn Step-0 typed/multi-hop slices green; untyped control unchanged. Full graph+cascade+
   profile-matrix regression gate.
2. **Embedder seeding seam** (`embed=`, Jaccard default) — Step-0 `semantic_seed` shows offline headroom only.
3. **Captained live seeding run** (work/, Brent-authorized) — the measured semantic accuracy claim, out of band.
4. **Neo4j backend** behind `uri=` — lazy import, fail-loud, shared contract, `FakeBoltDriver` tests
   (Cypher/params/`as_of`/`LIMIT`), id-set/order parity test.
5. **Captained live Neo4j parity run** (work/, Brent-authorized) — replay Step-0 eval against real Neo4j; DB
   proven a no-op on accuracy.

**Steps 0, 1, 4 are fully landable offline in CI. If only one thing lands, it's 0+1** (eval + typed edges) —
shipping Neo4j first delivers operational cost with zero measured accuracy gain (the trap every angle rejected).

## Risks carried forward
- **Eval-authorship trap:** blind multi-lens generation + deterministic calibration; enforce the headroom
  property as a committed assertion (too-easy case fails CI).
- **Regex coupling:** `classify_relation` is one named export with its own eval slice guarding mis-typing;
  never let `relates_to` silently mislabel a `depends_on` as `conflicts_with`.
- **Directional traversal is NOT byte-for-byte back-compat:** existing `test_graph_store.py` (e.g.
  `test_traverses_in_edges`) encodes undirected expectations → reconcile; untyped/`relates_to` keeps BOTH-way
  traversal to preserve them. Run graph + D008 cascade + profile-matrix as the regression gate (the cascade
  feeds `graph.search` hits into the exact-anchor gate).
- **Low typed-edge coverage on real bundles** — author purpose-built multi-hop typed fixtures; `relates_to`
  is a non-penalizing default.
- **Captain availability:** keep Steps 0, 1, 4 fully offline-landable so progress never blocks on a captained run.

## Key files
`eval/memeval/stores/graph_store.py` · `eval/memeval/okf.py` · `eval/memeval/router.py` ·
`eval/memeval/stores/embedders.py` · `eval/memeval/stores/sqlite_store.py` ·
templates: `stores/tests/test_d008_evals.py`, `test_semantic_retrieval_evals.py`, `test_embedders.py` ·
**new:** `eval/memeval/stores/tests/test_graph_retrieval_evals.py`
