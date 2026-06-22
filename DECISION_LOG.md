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

### D008 — (DESIGN ACCEPTED 2026-06-20 — building, eval-first) Meta-index / cascade retrieval over the OKF concept graph
- **Status:** proposed by Brent, **in Brent's domain** (all routing + memory; see [D009]). Design grounded against the real `router.py`/stores by an architect pass (2026-06-20) and the two open sub-decisions are now ruled (see below). Implementation underway, eval-first. No cross-team gate; Keith owns the primary agent that *calls* this, not the retrieval itself.
- **Idea:** treat the OKF link-graph as a meta-index (one concept space, three indexes joined by shared `item_id`); traverse the graph, return an exact node match, else fall through to the vector store via a node pointer. Known pattern = "recursive retrieval" (LlamaIndex `IndexNode`); cf. GraphRAG, HippoRAG (hippocampal-index theory).
- **Why it's attractive:** a *cascade* (try-one, fall-through) fits the project's efficiency thesis (single-route, no context flood) better than *fusion* (query-all + RRF). OKF gives the cross-store join almost for free.
- **Research (2026-06-19, two passes):** CONFIRMED a named pattern — LlamaIndex `IndexNode` + `RecursiveRetriever` ("recursive retrieval / node references"). The pointer-to-another-retriever is a dict lookup → **pure-stdlib implementable; no LlamaIndex/GraphRAG/Neo4j runtime dep** (those are references). There is **no off-the-shelf cross-paradigm meta-index** — unification is always app-level orchestration (our own code → good for the offline constraint).
- **The tension:** mature systems (GraphRAG, HippoRAG) chose **fusion** over cascade for recall-robustness, but **fusion (query-all + RRF) breaks our <10% efficiency budget by construction**. Cascade fits our thesis *only if* we de-risk its big failure mode: **silent wrong-success at the gate** — an exact-match stage that wrongly succeeds means the vector fall-through never fires and a better answer is silently lost. The gate is the single point of failure.
- **Mitigations (adopt):** instrument the gate day-1 (exact-hit vs fall-through rate; dangling-pointer check) — fits our observability standard; keep **RRF as a ~10-line stdlib tool (k=60) "in the box"** so we can flip to fusion/merge-rerank later; store the embedding/vector-id **on the OKF node** (an `x_` key) to approximate a unified store and kill dangling pointers.
- **Keystone:** cascade-vs-fusion is decided by **data, not opinion** — measure exact-hit precision on our OKF corpus via the routing/retrieval **eval set**, which de-risks both the v1 router and this decision. First-class deliverable.
- **Resolved (2026-06-19):** the D006-vs-D008 fork is settled by [D009] — the cascade fall-through lives **inside the router** (D008), instrumented.
- **Sub-decisions ruled (2026-06-20, AI-suggested by the architect pass → Brent-accepted):**
  - **Engagement scope:** the cascade engages **only when `classify(query)==GRAPH` and both graph+vector backends are registered**; markdown/vector queries keep today's single-route behavior. Implemented as a private `_GraphVectorCascade` `MemoryStore` wrapper returned by `Router.route()` → **no `[CONTRACT]` change** (schema/protocols stay frozen). This protects the 90% routing-eval semantics and stops an exact graph anchor hijacking a synthesis (vectors) query.
  - **Gate predicate (was open #1):** **exact-anchor gate** — graph "wins" only when rank-0 is a *unique exact anchor* (matched on `item_id` / OKF title/resource basename / quoted-or-backticked query span) that clears a calibrated score+margin floor; else fall through to vector. Conservative by design; **zero false-accepts on hard cases is the hard blocker** (the silent-wrong-success defense). Rejected: accept-any-non-empty (unsafe). Deferred to measurement only: verified/consult-2.
  - **Projection (was open #2):** **`item_id` hydration** — accepted graph hits become ranked `item_id`s, each hydrated via the vector store's `get(item_id)` (fall back to the graph item if absent), returned as `RetrievedItem`s with graph-derived scores (exact seed first, linked neighbors after). Pure stdlib. Deferred (would be `[CONTRACT]`): vector-rerank via a standardized `candidate_ids` filter; path/provenance on `RetrievedItem`.
  - **Still empirical (the keystone):** cascade-vs-fusion, decided by the D008 retrieval/gate eval set (false-accepts==0; gate precision@k==1.00; fall-through recovery within 2pts of vector-only; p95 memory-token overhead <10%). RRF stays a ~10-line stdlib consult-2 tool, never the front door.
  - **Build order:** PR1 = D008 retrieval/gate eval fixture + baseline reporter (no production code) — **SHIPPED as PR #17** (`stores/d008-eval-fixture`), gated FAIL→fix→PASS by an independent codex verifier (the first pass caught two non-adversarial "hard" cases; remediated with real decoys + a machine-checked anti-theater assertion). Baselines for PR2 to beat: graph-only recall@5 0.857 / MRR 0.619; vector-only recall@5 0.786 / MRR 0.690 (offline embedder). PR2 = `_GraphVectorCascade` + profile-ready `RouterConfig` — **MERGED as PR #23** (`router/d008-pr2-cascade`), gated FAIL→fix→PASS (the first review caught a stale anchor index + a stale memoized cascade — invisible to the passing tests; fixed + regression-guarded); default `Router()` byte-equivalent. PR2.5 = preset helpers + profile-matrix reporter; PR3 = spaCy + real-embedder adapters (eval-first).
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

---

### D016 — Router profiles/configuration seam (speed vs accuracy); spaCy + real embedder are accuracy-profile strategies behind seams
- **Context:** a team meeting (2026-06-20) decided the router should ship **multiple profiles/configurations — some optimizing for speed, some for accuracy.** Separately, a teammate proposed **spaCy** to lift router accuracy, and **OpenRouter is now a viable real embedder** (verified 2026-06-20: Qwen3 Embedding / Gemini Embedding 2 / Mistral Embed; the team already uses OpenRouter for the Daydreamer per architecture.md §7.3).
- **Decision:** model profiles as a **`RouterConfig` seam** — a named bundle of `{classifier strategy, embedder, gate thresholds (SCORE/MARGIN floors), cascade on/off, consult-2/RRF on/off, k}`. The **stdlib default = the "speed" profile** (rule-based classify + hashing embedder + cascade off/strict; zero-dependency). The **"accuracy" profile** injects heavier strategies *behind the existing seams*: a **spaCy/learned classifier** and a **real embedder** (Voyage/bge or OpenRouter) via `embed=`, cascade on, consult-2 for low-margin. So spaCy and the real embedder **never touch the default offline path** — same governance as `semantic-router` [D015] and real embeddings [D013].
- **Reframes the cascade build:** PR2 introduces a small `RouterConfig` so the cascade is **parameterized** (thresholds / on-off / injected embedder) = **profile-ready**; the full presets + spaCy/embedder adapters land as a thin layer after (PR2.5/PR3). Per-profile gate floors resolve the D008 calibration concern. **No `[CONTRACT]` change** (config + injection, contract frozen).
- **spaCy is gated eval-first:** adopt it only if it beats the stdlib rules on the routing eval set (the keystone principle; cf. [D008]). OpenRouter embedder is **not** needed for PR2 (the cascade is embedder-agnostic via `embed=`) — it's the accuracy profile's retriever + what the captained eval runs need (Brent's key + budget).
- **Design (architect pass 2026-06-20, grounded in the real `router.py`; two sub-decisions ruled):**
  - **Threading:** a frozen `RouterConfig` dataclass (+ `CascadeConfig`/`Consult2Config`) attached via a new **`Router.with_config(backends, config)`** factory — `Router.__init__`/`classify`/`explain`/`route` signatures **unchanged**, and `RouterConfig()` reproduces today's router byte-for-byte. No `schema.py`/`protocols.py` change.
  - **Classifier seam:** `RuleBasedClassifier` (default, wraps current `_score`) behind a small *internal* `RouterClassifier` protocol (not exported to `memeval.protocols`); spaCy/learned classifiers inject via lazy import, never on the default import path.
  - **Profiles = factory fns** (not an import-time registry): `speed_profile()` (==today), `balanced_profile()` (stdlib + cascade), `accuracy_profile(classifier=, embed=, …)`.
  - **RULED — cascade `write()`:** the `route()`-returned `_GraphVectorCascade` is **retrieval-only** — `search`/`get`/`all` work; `write()` **raises** (writes go through the store registry / save component, not a per-query dispatcher). Avoids double-write ambiguity. (AI-recommended → Brent-accepted.)
  - **RULED — `balanced` profile:** ships first as a **reporter row** in the PR2.5 profile matrix (isolates the cascade's standalone contribution); promoted to an official named preset only if the tradeoff curve shows cascade-on-stdlib measurably beats `speed`. Eval-first. (AI-recommended → Brent-accepted.)
  - **Requirements carried from the risk list:** identity/anchor index is O(n) per graph query → cache + invalidate on write; `as_of` must not leak future anchors through the gate/reason; real embedder changes vector dims → reindex; per-profile (not global) consult-2 thresholds.
  - **Sequencing (all `[CONTRACT]`-free):** PR2 = `_GraphVectorCascade` + profile-ready `RouterConfig` (default==today, gate ported from PR1, validated against the D008 fixture) — **MERGED as PR #23** → PR2.5 = preset helpers + profile-matrix reporter — **SHIPPED as PR #27** (`router/d008-pr2.5-profiles`; `speed_profile()`/`accuracy_profile()` + `test_profile_matrix.py`; matrix: balanced cascade = graph's recall 0.857 + vector's MRR 0.690 at single best-route cost, 0 hard false-accepts) → PR3 = spaCy/semantic-router + real-embedder adapters (eval-first acceptance), gated behind an eval-set-growth step (see [D018]).
- **AI involvement:** `accepted` — profiles were a **team mandate**; AI synthesized the unifying seam architecture (one config subsuming spaCy + real embedder + cascade), reframed PR2 to land profile-ready, and grounded it in the real router; Brent accepted the recommendation, ordering, and the two sub-decisions.
- **Why (defensible):** the router was already seam-designed (`embed=`/`uri=`/a contemplated learned-classifier slot), so profiles are just named bundles; the stdlib-default/zero-dep guarantee is preserved; it yields a measurable **speed↔accuracy tradeoff curve** on the eval set that directly exercises the headline `<10%` memory-token-overhead metric; heavy deps stay off the offline path.
- **Talking point:** "We turned 'speed vs accuracy' into one config seam — the offline stdlib path is the speed profile; the accuracy profile injects a real embedder and an NLP classifier behind the same seams — so the cascade and every heavy dependency are profile-gated, and I can plot the efficiency/accuracy tradeoff on my own eval set."

---

### D017 — Considered & scoped-out for v1: Interleaved Retrieval + Chain-of-Thought (IRCoT)
- **Context:** Brent read about **IRCoT** (interleave reasoning steps with retrieval — reason→retrieve→reason→retrieve, multi-hop; Trivedi et al. 2023) and asked whether it's worth exploring.
- **Decision (SCOPED OUT for v1):** do not adopt IRCoT now; log it as consciously-considered future work, owned conceptually by the primary agent (Keith) if ever pursued.
- **AI involvement:** `accepted` — Brent surfaced it; AI assessed and recommended scope-out with rationale; Brent agreed.
- **Why (defensible):** (1) **efficiency thesis** — IRCoT issues *multiple* retrievals + *multiple* reasoning turns, even more token-costly than the fusion we already rejected [D015] for breaking the `<10%` overhead budget; (2) **ownership boundary** — IRCoT is an *agent-level* reason↔retrieve loop (the agent deciding *if/when* to retrieve, repeatedly), which is **Keith's primary-agent territory**, not the router's *where/how* ([D009] if/where-how split). Our cascade's consult-2 fall-through is the lightweight, efficiency-preserving nod in that direction.
- **Talking point:** "I evaluated interleaved-retrieval-with-CoT and deliberately scoped it out for v1 — it's even more token-hungry than the fusion I already rejected, and it lives in the primary agent's reason-retrieve loop, not my router's where/how decision."

---

### D018 — Grow/diversify the routing+retrieval eval set BEFORE PR3 (don't overfit the bake-off)
- **Context:** PR3 swaps in learned classifiers (spaCy / semantic-router) + a real embedder behind the [D016] seam, adopted eval-first. But the routing eval is **31 self-authored** blind cases (router at 90%) and the D008 retrieval set is **8** — both small + self-authored (ROUTING_EVALS flags the bias). Brent asked whether to improve the **regex rules** first.
- **Decision (2026-06-20):** **No regex-tuning pass first — grow + diversify the eval set first.** Tuning rules against 31 cases we wrote ourselves optimizes a biased target (the self-confirming-eval trap an adversarial review already caught on PR1). The bigger, more adversarial set is the prerequisite that makes the PR3 bake-off (rules vs spaCy vs semantic-router) and the cascade numbers **defensible**, and it surfaces which regex misses are *cheap-fixable* (fix in the speed profile) vs *need-learning* (route to PR3). Sequencing: PR2.5 (done) → eval-set growth → PR3.
- **AI involvement:** `accepted` — Brent raised the regex question; AI recommended eval-growth-first with the overfitting rationale; Brent accepted.
- **Why (defensible):** eval-first ([D008] keystone); the known router misses (topical use of structural words; non-English relational verbs) are deliberately the rule/learning boundary, not a regex project; routing 90%→93% on a tiny set moves the headline memory metrics far less than retrieval quality (real embeddings + cascade) will.
- **Outcome — SHIPPED as PR #28:** blind multi-lens fan-out (5 firewalled generators × distinct lenses → synthesizer bucketed against the live router → fold) added **42 cases (eval grew 31→73)**. Buckets: 13 AGREE (5 golden-asserted), 9 GAP:cheap-fix, 3 GAP:needs-learning (multilingual), 17 contested(⚠). Added as a separate `D018_CASES` measured pool — existing assertions (28/31=90%, floor) mechanically untouched. The blind set scored **21/42=50%** and exposed the router's **markdown over-routing bias** — gaps the 31 self-authored cases never showed. Backlog tagged in-fixture (`note` field). Verifier CONCERNS→cleaned (demoted 2 incidental-pass multilingual cases out of the asserted golden pool).
- **Cheap-fix follow-up — SHIPPED as PR #29:** the 9 `GAP:cheap-fix` gaps resolved by 7 narrow router rules (value-of/gist→vectors; naming-"calling"→literal; touches/downstream→graph; env-var+URL literals→markdown; graph words inside quoted spans stripped before intent-matching; synth-command-object-rationale→vectors). **Speed profile rose 50%→73%** on the D018 set; golden 5→12 (fixes hard-asserted); **BLIND 28/31 unchanged (no regression)**. Gated build→FAIL(env tempdir + over-broad synth bonus)→harden(noun-as-object + 2 golden guards)→re-gate PASS. **Next:** PR3 (the 3 multilingual `GAP:needs-learning` + the 17 contested are PR3's eval-first targets).
- **Talking point:** "Before swapping in a learned router I grew the eval set — you can't claim a classifier 'beats the rules' on 31 cases you wrote yourself; that's the same self-confirming trap an adversarial review already caught me in once. The blind set immediately exposed a markdown over-routing bias the hand-written cases hid."

---

### D019 — Live Voyage embedding eval: real embeddings barely move the D008 fixture (the fixture, not the embedder, is the limit)
- **Context:** PR3b-1 (#41) shipped the Voyage `embed=` adapter. Ran a **live captained eval** (hashing FLOOR vs real `voyage-3-large`, dim 1024, doc/query asymmetry) over the D008 cascade/retrieval cases. (First key attempt 429'd on a free-tier RPM; Brent fixed the payment method → 2000 RPM → clean run.)
- **Result (7 graded cases, K=5):** vector recall@5 **0.786→0.786 (+0.000)**; vector MRR **0.690→0.714 (+0.024)**; cascade recall@5 **0.857→0.857 (+0.000)**; cascade MRR +0.024; fall-through recovery@5 **0.750→0.750 (+0.000)**. Net: a tiny ranking bump, **no recall/recovery gain**.
- **Adapter live-validated:** the run made real 200-OK calls to `api.voyageai.com` (auth, request shape, response parse, `input_type` payload all correct against the live API — confirms the gate's web-verification beyond the mocks).
- **Finding (the important part):** real embeddings barely helped because the **D008 fixture can't measure an embedder** — it's tiny (7 graded) and **lexically constructed** (decoys + gold built for the char-n-gram hashing embedder), so hashing already captures the signal; there's ~no semantic headroom for Voyage to add. The earlier "floor" framing was optimistic.
- **Implication / next:** the embedder swap is plumbed + validated, but its **value isn't demonstrable on this fixture.** To show Voyage's semantic advantage we need a **retrieval eval with semantic-divergence cases** (paraphrase/synonym queries where lexical overlap fails but meaning matches — a D018-style growth for *retrieval*, not routing), or to run on the **real benchmarks** (SWE-ContextBench / ContextBench) which carry genuine semantic queries. **Do NOT over-claim Voyage's benefit from the D008 fixture.**
- **AI involvement:** `measured` (eval-first) — the honest, anticlimactic result tempers the embedder-value claim and redirects effort to semantic eval coverage.
- **Talking point:** "I didn't assume the premium embedder helped — I measured it live. On my lexically-built fixture it barely moved recall (+0.02 MRR), which proved the fixture can't test semantics, not that Voyage is useless — the real test needs paraphrase cases or the live benchmarks."

---

### D020 — Semantic-divergence retrieval eval: real Voyage recovers 15/15 where hashing scores 0 (the embedder's value, finally measurable)
- **Context:** D019 showed the D008 fixture is too lexical to measure an embedder (live Voyage: +0.000 recall, +0.024 MRR). D020 is the response — a purpose-built **semantic-divergence retrieval eval**, shipped offline as **PR #44** (`eval/memeval/stores/tests/test_semantic_retrieval_evals.py`): **15 divergence cases** (query ≡ gold in meaning but little-to-no surface overlap — synonym / paraphrase / conceptual "why" / cross-lingual / abstraction) + **5 lexical controls**, over a 34-memory haystack. The committed offline path proves only **headroom** (offline hashing recall@5 **0.000** on divergence, **1.000** on control — machine-asserted, anti-theater); the embedder **measurement** is this captained live run.
- **Provenance (eval-first, blind):** cases authored by a blind multi-lens **Workflow** (6 firewalled generators × distinct lenses → synthesizer enforcing global gold-uniqueness → independent per-case semantic verifiers), then a **deterministic offline-embedder calibration** that DROPPED every "divergence" case the char-n-gram hashing embedder could already find (**12 of 27** generated — word-divergence ≠ char-trigram-divergence) and kept only the 15 it provably misses. Honesty controls baked into CI: the anti-theater tests + a fail-fast on unknown gold ids (the latter from a CodeRabbit catch). Cross-vendor Codex gate PASS before merge.
- **Result (live, hashing FLOOR vs `voyage-3-large` dim 1024, doc/query asymmetry, K=5):**
  - **Divergence: recall@5 0.000 → 1.000 (15/15 recovered); MRR 0.000 → 0.922.** Gold moved from outside top-5 (or absent) to **rank 0 in 13/15**, rank 1–2 in the other two.
  - **Control: recall@5 1.000 → 1.000; MRR 1.000 → 1.000** — no regression on the easy cases (Voyage didn't trade away lexical precision).
  - **Cross-lingual (es/fr/de query → English gold): all 5 recovered to rank 0** — voyage-3-large's multilinguality confirmed end-to-end (relevant to the 3 multilingual routing GAPs → PR3b-2).
- **Finding (the payoff):** the embedder's semantic value is **real and large** — it was the *fixture*, not the model, that hid it in D019. The same adapter that moved nothing on the lexical D008 fixture recovers **everything** on a fixture with genuine semantic headroom. This closes the D019 caveat: Voyage's benefit is now demonstrated, on an instrument whose every case is machine-proven to be beyond a lexical retriever. (Throwaway script: `work/voyage_semantic_eval_d020.py`.)
- **AI involvement:** `measured` (eval-first). AI orchestrated the blind generation, the deterministic calibration (which dropped 12/27 over-claimed cases), and the cross-vendor gate; the calibration + CodeRabbit's fail-fast are the honesty controls. Brent gated each step and authorized the live spend.
- **Talking point:** "I measured the premium embedder twice. On a lexically-built fixture it moved nothing (+0.000 recall) and I reported that honestly. Then I built a fixture with real semantic headroom — machine-proving each case is beyond a lexical retriever — and the same embedder recovered 15/15 (recall@5 0 → 1.0, MRR → 0.92). The lesson I'd defend in an interview: the measurement instrument matters as much as the model, and a 'premium' component's value is a claim you have to be *able to fail* to prove."

---

*All four owned components + the durable routing eval are logged. **Shipped/merged:** cascade (D008 — PR1 #17, PR2 #23); profiles+matrix (D016 — PR2.5 #27); eval growth (D018 — #28); cheap-fix router rules (#29); PR3a bake-off harness (#34); PR3b-1 Voyage embedder (#41, live-validated); semantic-retrieval eval (D019/D020 — **PR #44**, live-measured: divergence recall@5 **0.000 → 1.000**, 15/15). **Now:** D020 DONE — Voyage's semantic value demonstrated; embedder slice complete + measured. **Next:** PR3b-2 (semantic-router classifier, Voyage encoder — targets the 3 multilingual routing GAPs, now de-risked by D020's 5/5 cross-lingual recovery); optional spaCy adapter; adjudicate the 17 contested routing labels. **Considered & scoped-out:** fusion-by-default (D015), IRCoT (D017). **Future:** real benchmarks (SWE-ContextBench/ContextBench); router↔harness integration with Keith.*
