# Decision Log — Cookbook Memory (Brent / P3: stores + router)

Engineering & product decisions for my slice of the **agent-memory-harness** team project,
kept for the capstone **evidence pack** and interview defense (the AI-First Proof Standard:
*"can Brent ship with AI while staying in control of the product, codebase, evidence, and
tradeoffs?"*). I treat the AI like a fast junior engineer — it researches and proposes; I
decide and own the call.

**How to read an entry.** Each records the context, the options, the decision, **how the AI
was involved**, *why* it's defensible, and the one-line **talking point** I'd give in an
interview.

**AI-involvement tags:** `suggested` (AI proposed it) · `accepted` (I took the proposal as-is
after checking) · `changed` (I altered the proposal) · `rejected` (I declined the proposal).

---

## Slice 1 — `MarkdownStore` (merged: PR #5, commit `0bfe9e8`, 2026-06-19)

### D001 — OKF-native MarkdownStore (delegate to `OKFStore`) over a from-scratch store
- **Context:** My `stores/markdown_store.py` was a stub. A teammate (Ken) had already merged an
  OKF adapter (`okf.py`) whose `OKFStore` is a working `MemoryStore` persisting as an Open
  Knowledge Format bundle; his POC's suggested next step was "have Brent's MarkdownStore delegate
  to OKFStore + an inverted-keyword index."
- **Options:** (a) build a plain markdown+YAML store from scratch; (b) compose `OKFStore` and add
  the index on top; (c) subclass `OKFStore`.
- **Decision:** (b) — compose `OKFStore`, add the inverted keyword index.
- **AI involvement:** `accepted` — the AI surfaced the prior art and the team's intent; I
  confirmed OKF-native as the plan with the team before building.
- **Why (defensible):** the markdown backend's spec ("memory as markdown + YAML frontmatter")
  *is* OKF; delegating gives portability/cross-harness interchange and spec-conformance "for
  free," with less code to own. Composition (not subclassing) keeps the persistence swappable.
- **Talking point:** "Rather than reinvent a markdown store, I built on a teammate's OKF adapter
  so a run's memory is a portable, spec-conformant bundle — and I added the one thing it lacked:
  a fast keyword index."

### D002 — Keyword-only search (no zero-overlap padding), diverging from the reference store
- **Context:** The reference `InMemoryStore.search` scans all items and pads results up to `k`
  even with zero-overlap (score 0) filler. The `MemoryStore` protocol only requires results
  sorted by descending score with `rank`/`tokens` set and `as_of` honored — "top-k" means *up to* k.
- **Options:** (a) mirror the reference (always return k, padding with non-matches); (b) return
  only items sharing ≥1 query token; empty query → `[]`.
- **Decision:** (b) keyword-only.
- **AI involvement:** `accepted` (after challenge) — the AI recommended (b); I asked it to walk
  through the exact behavioral difference before agreeing, then chose (b) deliberately.
- **Why (defensible):** aligns with the project's own metrics — **Relevancy** ("retrieved items
  actually relate") and **Efficiency** (memory-token overhead): filler items are tokens that
  don't relate. It also matches the markdown backend's defined role (*literal recall*). The
  "lost recall" is illusory — a score-0 item ranked last isn't a real retrieval — and semantic
  gaps are intentionally the vector store's + router's job. Ranking formula/tie-breaks still
  mirror the reference so cross-backend comparisons stay fair. (Coordinate: callers must tolerate
  fewer than k results — confirm with Keith's retrieval orchestrator.)
- **Talking point:** "My keyword backend returns only genuine matches, not padding — that's the
  honest behavior for literal recall and it protects the relevancy and efficiency metrics the
  whole project is judged on."

### D003 — Re-implement `_tokenize` locally (self-contained module) + a parity test
- **Context:** Ranking must match the reference, which uses a private `harness._tokenize`.
- **Options:** (a) import `harness._tokenize` (single source, but couples to a teammate's private
  symbol); (b) re-implement the ~10-line stdlib tokenizer in my module and guard parity with a test.
- **Decision:** (b).
- **AI involvement:** `suggested` — the AI proposed the self-contained approach; I accepted.
- **Why (defensible):** keeps the backend modular ("each module carries its own dependencies")
  and avoids importing another owner's private internals; a parity test fails loudly if the two
  tokenizers ever drift. Promoting `_tokenize` to a shared util later is a clean follow-up.
- **Talking point:** "I avoided reaching into a teammate's private function — I kept my module
  self-contained and added a test that pins ranking parity, so we get safety without coupling."

### D004 — Tests live in my owned path, not the shared test dir
- **Context:** Project rule = tests-before-code, but `eval/tests/` is owned by Ken (CODEOWNERS).
- **Decision:** put my 9 `unittest` cases under `eval/memeval/stores/tests/` (my owned path),
  stdlib-only.
- **AI involvement:** `suggested`/`accepted`.
- **Why (defensible):** respects one-owner-per-directory so my PR only touches files I own (clean,
  non-conflicting, mergeable); stdlib-only matches the project's zero-dependency offline guarantee.
- **Talking point:** "I kept my PR strictly inside the paths I own and matched the project's
  zero-dep testing style — the collaboration model, not just the code, mattered."

### D005 — Build against current paths now; defer the OKF package extraction (ADR-P1)
- **Context:** A merged ADR (`docs/harnesses/05-plugin-mvp-plan.md`, ADR-P1) proposes extracting
  `stores/`/`router.py`/`dreaming/` into a standalone `cookbook_memory/` package — but flags the
  move as a team decision needing my + Scott's + Ken's sign-off.
- **Decision:** build `MarkdownStore` in-place against the current frozen scaffold; treat the
  extraction as a separate, later team call.
- **AI involvement:** `accepted` — AI flagged the ADR; I took it to the team, who confirmed
  build-in-place.
- **Why (defensible):** the ADR itself sanctions building against current paths until the move
  happens, and the work moves with the package if/when extraction occurs — so nothing is wasted
  and I didn't block on an unscheduled refactor.
- **Talking point:** "I shipped against the agreed current structure instead of pre-empting a
  refactor that's still a pending team decision."

---

## Router design (v1 shipped; cascade/meta-index still open)

### D006 — Retry-on-empty belongs to the primary agent, not our router
- **⚠ SUPERSEDED (2026-06-19) by [D009]:** reclassified — a fallback/cascade search is a *where/how* concern, so it's the **router's** job, not the primary agent's. Kept for the reasoning trail.
- **Context:** Our router does single-best-backend dispatch (no fan-out, per architecture). Keyword-only markdown can legitimately return `[]`. So: who decides to retry against a different backend?
- **Decision:** The **primary agent** (Keith's coding agent) owns the retry decision. Our `route()` stays a pure best-first dispatcher with graceful fallback to an *available* backend — it does not loop or retry on empty results.
- **AI involvement:** `suggested` — the AI raised the ownership question; I decided.
- **Why (defensible):** keeps the router single-responsibility and deterministic; the primary agent has the full task context and cost budget to judge whether a retrieval was "good enough," which the router does not. Avoids burying hidden multi-backend cost inside a component whose entire point is single-route efficiency.
- **Talking point:** "My router makes one best-first routing decision; whether to retry elsewhere is the calling agent's call, because it owns the task context and the budget — my component stays a clean, deterministic dispatcher."

---

### D007 — Router roadmap: rule-based/deterministic v1 → fine-tuned local LLM north star
- **Context:** The routing *decision mechanism* can be hand-written rules or learned.
- **Decision:** v1 (this sprint) = rule-based, deterministic, stdlib-only. North star (likely post-deadline) = a **fine-tuned local LLM** making the routing/traversal decision. `semantic-router` is a possible cheaper interim learned step.
- **AI involvement:** `accepted` — Brent's roadmap; AI noted `semantic-router` as an interim and surfaced the offline/determinism constraints.
- **Why (defensible):** deterministic rules are testable, free, offline, and shippable now; a learned router is only worth it once routing accuracy can be *measured* (the routing eval set) and there's time/data to fine-tune. Scoping ambition to the deadline is the call.
- **Talking point:** "v1 routing is deterministic rules I can test and defend; the north star is a fine-tuned local model — but I scoped that out of the sprint deliberately rather than ship something I couldn't measure or run offline."

### D008 — (OPEN) Meta-index / cascade retrieval over the OKF concept graph
- **Status:** proposed by Brent, **in Brent's domain** (all routing + memory; see [D009]) — an architecture direction not yet implemented. No cross-team gate; Keith owns the primary agent that *calls* this, not the retrieval itself.
- **Idea:** treat the OKF link-graph as a meta-index (one concept space, three indexes joined by shared `item_id`); traverse the graph, return an exact node match, else fall through to the vector store via a node pointer. Known pattern = "recursive retrieval" (LlamaIndex `IndexNode`); cf. GraphRAG, HippoRAG (hippocampal-index theory).
- **Why it's attractive:** a *cascade* (try-one, fall-through) fits the project's efficiency thesis (single-route, no context flood) better than *fusion* (query-all + RRF). OKF gives the cross-store join almost for free.
- **Research (2026-06-19, two passes):** CONFIRMED a named pattern — LlamaIndex `IndexNode` + `RecursiveRetriever` ("recursive retrieval / node references"). The pointer-to-another-retriever is a dict lookup → **pure-stdlib implementable; no LlamaIndex/GraphRAG/Neo4j runtime dep** (those are references). There is **no off-the-shelf cross-paradigm meta-index** — unification is always app-level orchestration (our own code → good for the offline constraint).
- **The tension:** mature systems (GraphRAG, HippoRAG) chose **fusion** over cascade for recall-robustness, but **fusion (query-all + RRF) breaks our <10% efficiency budget by construction**. Cascade fits our thesis *only if* we de-risk its big failure mode: **silent wrong-success at the gate** — an exact-match stage that wrongly succeeds means the vector fall-through never fires and a better answer is silently lost. The gate is the single point of failure.
- **Mitigations (adopt):** instrument the gate day-1 (exact-hit vs fall-through rate; dangling-pointer check) — fits our observability standard; keep **RRF as a ~10-line stdlib tool (k=60) "in the box"** so we can flip to fusion/merge-rerank later; store the embedding/vector-id **on the OKF node** (an `x_` key) to approximate a unified store and kill dangling pointers.
- **Keystone:** cascade-vs-fusion is decided by **data, not opinion** — measure exact-hit precision on our OKF corpus via the routing/retrieval **eval set**, which de-risks both the v1 router and this decision. First-class deliverable.
- **Resolved (2026-06-19):** the D006-vs-D008 fork is settled by [D009] — the cascade fall-through lives **inside the router** (D008), instrumented. **Still open (Brent-owned design):** how a graph hit projects into a ranked candidate (graph returns nodes/paths, not a ranked doc list); and cascade-vs-fusion, decided empirically via the routing/retrieval eval set.
- **Talking point (if pursued):** "I framed our three backends as one concept graph with cascade fall-through — a recursive-retrieval meta-index — which matches the efficiency goal better than fan-out-and-fuse."

---

### D009 — Ownership rule: primary agent decides IF; router decides WHERE & HOW (supersedes D006)
- **Context:** We needed a clean axis for who owns retrieval/storage decisions. (Also corrects an earlier confusion: per our terms **all routing + memory is Brent's**; Keith owns the **primary agent**, not a "retrieval orchestrator.")
- **Principle (team rule):** the **primary agent decides IF** something is stored/retrieved at all; the **router decides WHERE and HOW** it is stored/retrieved.
- **Resolution of the D006/D008 fork:** a fallback/cascade search across backends is a where/how question → the **router's** job, not the primary agent's (D006 mis-filed it as an "if"). The graph→vector fall-through therefore lives **inside the router** (D008 direction), where its gate can be instrumented. **(Shipped today: `route()` does single best-first dispatch + graceful fallback to an available backend, D003; the structural cascade is D008 — designed, not yet built.)** The primary agent's only retrieval input is "retrieve, yes/no."
- **AI involvement:** `changed` — the AI first framed the fallback as the primary agent's "if" decision (D006); Brent reclassified it as a where/how concern owned by the router.
- **Why (defensible):** clean single-axis ownership; the router holds all cross-backend knowledge needed to decide where/how, and keeping the cascade inside the router makes its gate measurable (vs. an opaque agent retry).
- **Talking point:** "We drew the line at if-vs-where/how: the agent decides whether to remember or recall; my router owns everything about where and how — including cascading across backends — so retrieval lives in one observable place."

---

### D010 — Scored-signal classifier over first-match if/elif rules (router v1)
- **Context:** v1 router maps a query to one of {graph, vectors, markdown}, deterministically and offline.
- **Decision:** a **scored-signal** classifier — cheap signal functions add to a per-backend score; argmax wins; ties + no-signal → the semantic default (vectors). Shipped in PR #6.
- **AI involvement:** `accepted` — AI recommended scored-signals over brittle first-match rules; Brent agreed.
- **Why (defensible):** order-independent and robust (overlapping signals don't fight); yields a **confidence/margin** for free (top-two gap = the fusion-trigger signal, toward D008); observable (`explain()` exposes the scores); and it's the same shape a learned classifier (D007) slots into behind `route()`. Intent signals outweigh code-token signals so "why &lt;code_token&gt;" stays semantic (passes the adversarial cases).
- **Talking point:** "I scored each backend from cheap signals and took the argmax instead of brittle if/elif rules — order-independent, it hands me a confidence margin I can later use to trigger fusion, and a learned model drops into the same seam."

---

### D011 — Hardened the router with blind adversarial subagents (round 1)
- **Context:** v1 passed 100% of the self-authored seed — suspicious (self-confirming). Needed an unbiased stress test.
- **Decision:** spawn 4 subagents **firewalled from `router.py`** (lenses: surface traps, ambiguity, messy/real, boundary) to generate 41 blind adversarial queries; run them through the router; fix the clean bugs eval-first.
- **Result:** **58% → 83%** on hard cases (0 crashes, no seed regressions). Fixes: `import`/impact graph signals, broadened `relate`, dropped `using` false-positive, `called`→literal, `name for`, zero-token guard. Remaining misses are contested (Bucket B, pending Brent) or known semantic limitations (topical "connect to", non-English) — not clean bugs.
- **AI involvement:** `accepted` / `changed` — Brent directed the blind-generation approach; the blind queries forced several rule corrections the seed never would have.
- **Why (defensible):** blind generation defeats the self-confirming-eval trap; measuring before/after turns "I improved it" into a number; the residual misses are honestly catalogued (contested vs ceiling vs limitation), not hidden.
- **Talking point:** "I didn't trust my own 100% — agents that couldn't see my code wrote adversarial queries that dropped me to 58%, I fixed the real bugs back to 83%, and catalogued the rest as genuine ambiguity or known limits."

---

### D012 — Bucket B adjudication: trim two greedy graph signals; "everything about X" → vectors
- **Context:** the blind adversarial round (D011) surfaced 3 contested cases where the router's graph signals stole conceptual queries.
- **Decisions (Brent):**
  - *"compare X to Y"* → **vectors** (synthesis, not a structural edge) — move `compare` from the graph signals to vectors.
  - *"tradeoff / difference **between** X and Y"* → **vectors** — drop the `between…and` graph signal (a false-positive magnet; `tradeoff` already routes vectors).
  - *"everything we know about X"* → **vectors** for v1, and explicitly a **fusion candidate** for the cascade (D008) — it really wants all backends.
- **AI involvement:** `accepted` — AI flagged the greedy graph signals + recommended these; Brent ruled.
- **Why (defensible):** "compare" and "X between Y" read as structural but usually mean "synthesize this for me"; trimming them removes a class of false-positives. "everything about X" is honestly a fusion case — single-route picks vectors and we note the ceiling instead of pretending.
- **Talking point:** "Blind testing showed my graph rules were greedy — 'compare' and 'X between Y' look structural but mean 'synthesize this,' so I routed them to the semantic store and flagged 'everything about X' as a true fusion case for later."

---

### D013 — SqliteVectorStore: stdlib char-n-gram embedder offline; real embeddings deferred
- **Context:** the vector backend needs dense semantic similarity, but the offline path must be zero-dependency.
- **Decision:** v1 is stdlib-only — `sqlite3` + a deterministic char-n-gram feature-hashing embedder + brute-force cosine. Real dense embeddings (Voyage/bge, PRD §7.1) + ANN (HNSW/FAISS) inject behind the `embed=` seam on the paid path. Shipped PR #9.
- **AI involvement:** `accepted` — AI offered three options (stdlib lexical / pure placeholder / real-embeddings-now); Brent chose the stdlib char-n-gram option.
- **Why (defensible):** keeps the offline test path dep-free and deterministic; char-n-grams give fuzzy/morphological similarity the keyword store can't, so the backend is distinguishable even offline; honest that offline ≠ dense-semantic (that's a paid-path eval).
- **Talking point:** "My vector store is real plumbing — sqlite + a hashing embedder + cosine — that swaps to Voyage/bge by injection, zero deps on the offline path."

### D014 — GraphStore: in-memory link-graph traversal; typed/Neo4j deferred
- **Context:** the graph backend serves relationship queries (the router sends them here).
- **Decision:** v1 is stdlib + in-memory — memories are nodes, OKF links (`metadata["okf_links"]`) are edges; `search` = seed (token overlap) → BFS-traverse the neighborhood, scoring `seed_overlap * decay**distance`. A typed-edge graph DB (Neo4j) + persistence are deferred behind the `uri=` seam. Shipped PR #10.
- **AI involvement:** `accepted` — AI proposed the seed-then-traverse design + the OKF-links-as-edges mapping; Brent accepted.
- **Why (defensible):** delivers the distinctive value (a query matching one node also surfaces its *linked* neighbors — relationship retrieval the keyword/vector backends can't do) with zero deps; honest that v1 edges are untyped (OKF links carry no type) and traversal undirected.
- **Talking point:** "The graph store makes 'what's connected to X' work — it returns X's linked neighborhood, not just keyword matches — reading the OKF link graph our markdown store already writes."

### D015 — Rejected: fusion-by-default (query-all + RRF) as the retrieval architecture
- **Context:** the research (D008) surfaced three multi-retriever architectures — routing, cascade, fusion.
- **Decision (REJECTED):** the AI/research presented fusion (query every backend, merge with Reciprocal Rank Fusion) as the highest-recall option — what GraphRAG/HippoRAG converged on. **We rejected it as the default.**
- **AI involvement:** `rejected` — Brent rejected the AI-surfaced fusion-default in favor of routing + (future) cascade. (Also rejected `semantic-router` on the offline path — not stdlib-safe.)
- **Why (defensible):** fusion queries all three backends every time and floods context — it breaks the headline metric (memory-token overhead < ~10%) by construction. Routing (one retrieval, flat cost) fits the efficiency thesis; RRF stays a ~10-line stdlib tool for the rare cascade-consults-2 case, not the front door.
- **Talking point:** "I rejected fan-out-and-fuse even though it's the recall-maximizing default in the literature — it would have blown the token-efficiency budget, which is the whole hypothesis."

---

*All four owned components + the durable routing eval are logged. Future: cascade/meta-index (D008); captained eval runs (real embeddings + keys); router↔harness integration with Keith.*
