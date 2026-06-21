# CONTEXT — Brent's slice of agent-memory-harness ("Cookbook Memory")

> Front door for picking this up in a fresh session. Last updated 2026-06-19.

## What this is
A 4-person team project: a model-agnostic **persistent memory harness** for long-running
coding agents. Hypothesis: Haiku + the harness beats Opus 4.8 (no memory) on ≥2 of 5 public
memory benchmarks, with <~10% memory-token overhead, across 4 metrics (Recency, Efficiency,
Relevancy, Accuracy). Shared repo: github.com/kenhuangus/agent-memory-harness (**GitHub, not GitLab**).

**Brent (@bgibson1618) is P3** — owns `eval/memeval/stores/` (markdown / sqlite-vector / graph
backends) + `eval/memeval/router.py`. Teammates: Keith @kmazanec (harness/OpenCode), Ken
@kenhuangus (eval infra + repo owner), Scott B. @NerdAlert58 (dreaming).

## Workspace split (important)
- **`~/projects/agent-memory-harness`** — the SHARED code repo. Brent's real deliverables live
  here; changes ship via small PRs on `stores/*` / `router/*` branches.
- **`~/projects/capstone-workspace`** (this dir) — Brent's PRIVATE planning/evidence/scratch,
  NOT in the shared repo. Holds: this `CONTEXT.md`, `DECISION_LOG.md` (D001–D019, the AI
  suggested/accepted/changed/rejected log), `ROUTING_EVALS.md`, `TEAM_NOTES.md`, and `work/` (gitignored
  scratch: delegate run dirs + throwaway eval scripts). The agent file-memory (`memory/` + `MEMORY.md`)
  lives separately under `~/.claude/projects/-home-brent-gibson-projects-capstone-workspace/memory/`
  (auto-loaded each session), NOT in this dir. Demo/info material made here may target **Nerdy**
  (tentative — not folded into any plan yet).

## Current state: core build SHIPPED; D008 cascade + profiles + PR3 extension IN PROGRESS (see Active work)
The original four owned components are implemented, **stdlib-offline** (real paths behind lazy injection
seams), **eval-first**, independently reviewed, and squash-merged to `main` (PRs **#5–#12**). Since then a
larger extension arc (cascade meta-index, speed/accuracy profiles, eval growth, learned classifiers +
real embedder) has shipped PRs **#17, #23, #27, #28, #29, #34, #41** — current detail in **Active work** below.
- `MarkdownStore` (#5) — OKF-native (delegates to `okf.OKFStore`) + inverted keyword index; keyword-only search (no padding).
- `router.py` (#6) — rule-based scored-signal dispatch to one backend; hardened vs blind adversarials (#7, 58%→83%); Bucket B contested labels adjudicated (#8).
- `SqliteVectorStore` (#9) — `sqlite3` + a deterministic char-n-gram hashing embedder + brute-force cosine; real embeddings (Voyage/bge) + ANN behind `embed=`.
- `GraphStore` (#10) — in-memory link-graph traversal; OKF links (`metadata["okf_links"]`) = edges; seed-then-BFS retrieval. Neo4j behind `uri=`.
- Durable blind routing-eval fixture (#11) + a self-contained-refs cleanup (#12).

`main` is clean and synced; all tests green. An independent `/sanity` (Codex) pass was run and
its findings remediated (durable eval committed, docs reconciled, team items captured below).

## Active work: D008 cascade + router profiles + PR3 learned-path — IN PROGRESS (updated 2026-06-21)
Building the D008 cascade + the speed/accuracy profile seam, eval-first, run as the **agent-roster
orchestrator** (delegating to architect/implementer/verifier roster runs; see DECISION_LOG D008 +
D016 for the ruled design, D017 for IRCoT scoped-out).
- **PR1 — MERGED (#17):** D008 retrieval/gate eval fixture + baseline reporter
  (`eval/memeval/stores/tests/test_d008_evals.py`), no production code. Gated FAIL→fix→PASS (first
  pass caught two non-adversarial "hard" cases; fixed + machine-checked anti-theater assertion).
  Baselines: graph-only recall@5 0.857 / MRR 0.619; vector-only 0.786 / 0.690 (offline embedder).
- **PR2 — MERGED (#23)** (`router/d008-pr2-cascade`): `_GraphVectorCascade` + profile-ready
  `RouterConfig` in `router.py`. Cascade is **off by default** (`RouterConfig()`==today, byte-equivalent;
  routing still 28/31=90%); engages only when a cascade-enabled profile + `classify==GRAPH` + both
  backends. Exact-anchor gate (else fall through) + `item_id` hydration; retrieval-only (`write()`
  raises); `as_of` no-leak. Gated FAIL→fix→PASS (first review caught a stale anchor index + a stale
  memoized cascade — both invisible to passing tests; fixed + 5 regression tests). No `[CONTRACT]` change.
- **PR2.5 — MERGED (#27)** (`router/d008-pr2.5-profiles`): `speed_profile()`/`accuracy_profile()`
  presets + `test_profile_matrix.py` (the committed speed↔cascade tradeoff matrix). Matrix (offline
  embedder, 8 cases): speed recall@5 0.857/MRR 0.619/220 tok; balanced cascade 0.857/0.690/75% recovery/
  0 hard false-accepts/251 tok. `balanced` is a reporter row (not a public preset); `accuracy` is an
  honest PR3 placeholder (runs only when classifier+embed injected). Gated build→FAIL(commit-state +
  accuracy-honesty)→fix→re-gate PASS. No `[CONTRACT]` change. **Process note:** realigned to
  *commit-then-gate* (the FAIL surfaced the drift).
- **D018 eval-growth — MERGED (#28)** (`stores/d018-routing-eval-growth`): routing eval grown **31→73**
  via blind multi-lens fan-out (5 firewalled generators → synth → fold), as a separate measured
  `D018_CASES` pool (existing 28/31=90% + floor untouched). Exposed the router's **markdown
  over-routing bias**. Backlog tagged in-fixture: cheap-fix=9, multilingual→PR3=3, contested=17.
- **Cheap-fix router rules — MERGED (#29)** (`router/d018-cheap-fixes`): 7 narrow rules in
  `router.py` resolved all 9 `GAP:cheap-fix` gaps → **speed profile 50%→73%** on the D018 set; golden
  5→12 (fixes hard-asserted); **BLIND 28/31 unchanged**. Gated FAIL(env tempdir + over-broad synth
  bonus)→harden→PASS. No `[CONTRACT]` change.
- **PR3a (bake-off harness) — MERGED (#34):** `test_routing_bakeoff.py` — stdlib/CI-safe harness
  scoring classifier strategies vs the dynamic rules baseline (registry: rules + fake + spaCy/
  semantic-router SKIP stubs; eval-first `eligibility()` bar; per-bucket matrix). Full PR3 design at
  `work/agents/pr3-arch/architect/output.md`.
- **PR3b-1 (Voyage real-embedder) — MERGED (#41)** (`stores/pr3b-voyage-embedder`):
  `embedders.py` (`VoyageEmbedder` stdlib urllib/no-SDK, voyage-3-large dim 1024, key at call-time,
  retries incl. timeouts, no network at import; `MockEmbedder`; `rebuild_store`) + the `embed=` seam
  carrying `input_type` document/query asymmetry via signature introspection (offline default
  byte-identical). **Decision: Voyage over OpenRouter** for embeddings (MTEB-leader, code-aware, PRD pick;
  OpenRouter can't serve Voyage). Mock-tested; gated by a 4-lens adversarial Workflow (web-verified vs
  Voyage's API; 2 real bugs fixed). Key in `~/projects/capstone-workspace/.env` (`VOYAGE_API_KEY`).
- **Live captained run — DONE (DECISION_LOG D019):** ran hashing FLOOR vs real Voyage (voyage-3-large,
  dim 1024) over the D008 cascade cases. Result: vector recall@5 0.786→0.786, MRR 0.690→**0.714 (+0.024)**,
  cascade recall@5 0.857→0.857, fall-through recovery 0.750→0.750 — a tiny ranking bump, **no recall gain**.
  Adapter **live-validated** (real 200-OK calls to Voyage; first key attempt 429'd on free-tier RPM →
  Brent fixed payment → 2000 RPM → clean run). **Finding:** the D008 fixture is too small + *lexical* to
  measure an embedder; the value can't be shown on it. (Throwaway scripts: `work/voyage_live_eval*.py`.)
- **NEXT — semantic retrieval eval growth (per D019) — the single next task:** author paraphrase/synonym
  retrieval cases (lexical hashing fails, meaning matches) → re-baseline hashing vs Voyage to actually
  measure the embedder; OR run the real benchmarks (SWE-ContextBench/ContextBench). **Do not claim
  Voyage's benefit until this exists.**
- **THEN:**
  - **PR3b-2** — `SemanticRouterClassifier` using `VoyageEmbedder` as its encoder + taxonomy exemplars
    → routing bake-off vs rules (targets the 3 multilingual GAPs).
  - **spaCy adapter** (optional, no key; install-heavy de/zh/fr models) — alt multilingual route.
  - The **17 contested** routing labels stay measured; adjudicate in a separate pass.
- **Resume:** **all PRs merged**; `main` @ `7ecd52d` (#41), local on `main`, clean. Pick up at the
  **semantic retrieval eval growth (D019)**.

## How to verify (run from `~/projects/agent-memory-harness/eval`)
- Smoke gate (the team's CI check): `python3 tests/test_smoke.py` → **73 passed / 0 failed / 1 skipped** as of 2026-06-21 (count grows as the team adds tests — the contract is 0 failed; was 67→71→73).
- D008 retrieval/gate fixture: `python3 -m memeval.stores.tests.test_d008_evals` (report) · `... -m unittest ...` (now on `main`). Cascade tests: `test_d008_cascade`; profile matrix: `test_profile_matrix`; bake-off: `test_routing_bakeoff`; Voyage embedder: `test_embedders`.
- Brent's suites: `python3 -m unittest memeval.stores.tests.test_markdown_store memeval.stores.tests.test_sqlite_store memeval.stores.tests.test_graph_store memeval.stores.tests.test_router memeval.stores.tests.test_routing_evals`
- Reproduce the routing number: `python3 -m memeval.stores.tests.test_routing_evals` → **28/31 = 90%** agreement on the blind hard cases.
- Env: `python3` + `uv` (no `python`/`pip` on PATH). The offline path is zero-dependency.

## What's next (see Active work above for the live build state + the single next task)
1. **Cascade / meta-index + profiles (D008/D016)** — *SHIPPED & merged* (PR1 #17 → PR3b-1 #41). The single next task is the **semantic retrieval eval growth (D019)**, then **PR3b-2** — see **Active work**. Brent's domain.
2. **Captained eval runs** — SWE-ContextBench + ContextBench (Brent's), on **real embeddings** + his own API key. Needs the deferred env setup (uv venv + Voyage/bge + ANN index). Run via the repo's GitHub Actions **Benchmark run** workflow (`.github/workflows/benchmark.yml`) on Brent's own key (repo secret `ANTHROPIC_API_KEY_BGIBSON1618`; $10 default budget) — see `collaborate.html` / `plan.md`. **Optional** — the build doesn't depend on it.
3. **router↔harness integration** — coordinate the seam with Keith's harness. The router exposes `route(query) -> MemoryStore`, `classify(query) -> backend-name`, and `explain(query)` (scores + margin); the seam is Keith's primary agent calling `route()` (per the if/where-how split: the agent decides *if* to retrieve, the router decides *where/how*). No owner/branch/acceptance defined yet — coordinate with Keith.
4. **Team-coordination items** — see `TEAM_NOTES.md`: (a) version-invariant (`architecture.md` vs the stores), (b) `project-plan.md` overstates shipped production pieces.
5. **Capstone closeout** — evidence-pack readiness (`/evidence-pack`), a Nerdy-aimed demo (`/demo`).

## Working conventions
- GitHub Flow; short-lived branches; small PRs; edit only owned paths; don't reformat others' files.
  Frozen contract (`schema.py`/`protocols.py`) changes only via a `[CONTRACT]` PR with all 4 owners.
  Branch protection is non-blocking (any collaborator can squash-merge; CodeRabbit/CI are signals).
- **Pre-push checkpoint:** commit locally → a fresh `verifier` subagent reviews the diff → show the
  filled PR checklist + Notes + verdict → get an explicit "go" → push. **Never auto-push.**
- **Eval-first:** write the eval/tests before the code.
- Design is provisional — surface better ideas as "possible new paths," don't silently conform or discard.
- The capstone `DECISION_LOG`/`ROUTING_EVALS` stay **private** (here); shared code is self-contained (no pointers back to these).
