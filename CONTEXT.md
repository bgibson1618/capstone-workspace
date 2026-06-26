# CONTEXT — Brent's slice of agent-memory-harness ("Cookbook Memory")

> Front door for picking this up in a fresh session. Last updated 2026-06-24.

## What this is
A 4-person team project: a model-agnostic **persistent memory harness** for long-running
coding agents. Hypothesis: Haiku + the harness beats Opus 4.8 (no memory) on ≥2 of 5 public
memory benchmarks, with <~10% memory-token overhead, across 4 metrics (Recency, Efficiency,
Relevancy, Accuracy). Shared repo: github.com/kenhuangus/agent-memory-harness (**GitHub, not GitLab**).

**Brent (@bgibson1618) is P3** — owns `eval/memeval/stores/` (markdown / sqlite-vector / graph
backends) + `eval/memeval/router.py`. Teammates: Keith @kmazanec (harness/OpenCode), Ken
@kenhuangus (eval infra + repo owner), Scott B. @NerdAlert58 (dreaming).

## ⭐ NORTH STAR — THIS OVERRIDES EVERYTHING BELOW IT (set by Brent; re-affirmed emphatically 2026-06-24)
**WE ARE BUILDING THE BEST MEMORY ROUTER WE CAN. FULL STOP.** That is the only fixed point. Every other line in this doc, every `DECISION_LOG` entry, every ADR, and **`architecture.md` itself** is SUBORDINATE, provisional, and often stale. Do NOT treat any of them as a constraint on doing the better thing.

- **Build like every option is on the table — because it is. Constraints are NEGOTIABLE.** Heavier/paid/native deps (FalkorDB, sentence-transformers, sqlite-vec, usearch, Voyage, rerankers, a learned router) are all fair game if they make the router better. Stdlib-offline is a CI convenience (an air-gapped test path), **never a feature ceiling** — if it ever blocks the best system, the system wins.
- **ALL previous decisions are subject to change given new information.** The `DECISION_LOG` is a record, NOT a contract. Contradict and RETIRE any of it (D013/D021/D022/D028/D039/D043/D044 — anything) the moment a better path appears. A past decision is never a reason to not do the better thing.
- **`architecture.md` is STALE — do not trust it as a spec.** Treat it as historical. If reality and the doc disagree, reality wins; fix the doc later, don't let it veto the build.
- **Code is rewritable.** Whole sections (the router classifier, a store backend, the shared scorer / cross-backend parity model) get rewritten if that's what "best" needs. *(Example, this session: reranking was moved out of a build-layer helper INTO the router config because that's where it belongs — D045.)*
- **Only TWO real constraints:** (1) **empirical merit** — the SWE-Bench-CL `make pipeline` run is the arbiter; build options and let the benchmark decide; (2) **engineering correctness** — known bugs/hazards (MATCH-never-MERGE, the ANN `ORDER BY` ranking bug, cross-process index coherence) are problems to SOLVE, not excuses to defer.
- **Posture: build, measure, keep the best.** Bias HARD toward standing options up — never defer on effort/precedent/current-scale. If the benchmark can't yet show an upgrade's value (e.g. ANN over a tiny store), SCALE THE EVAL WORKLOAD so it's measurable; don't skip the upgrade. (See memory `north-star-best-system`, `build-in-parallel-not-babysit`.)

## Eval philosophy — what actually matters (2026-06-24)
We build out the eval set as we go — fast offline "unit evals" (the routing bake-off, retrieval evals) run between full pipeline runs — **but those results are provisional data points, not verdicts.** The **only** metric that decides anything is the **SWE-Bench-CL pipeline** (`make pipeline`). Until we get real SWE-Bench-CL feedback, **keep every option on the table** — do not over-fit to, or descope candidates based on, the small unit-eval sets. *(Concretely: routing evals are **English-focused for now**; non-English / multilingual cases are **deferred** — the `GAP:needs-learning` bucket is a 3-case multilingual edge the English coding workload doesn't exercise, and semantic routing's only measured edge over rules is on exactly those.)*

## ⭐ 2026-06-26 SESSION — read this FIRST (most recent)
**Shipped + MERGED today:** FalkorDB **PR1 #193** (parity floor) + **PR2 #200** (opt-in `native=True` typed-graph mechanism); xarray accum **evidence #196** (text: builtin 5/22 → plugin-accum 6/22, memory +1 again, D057) + **#199** (the memory-store DBs) + **#201** (plugin-blank seed DBs); **ui inspector tweaks #203** (muted the cosmetic nested-dir warning + added a sortable/filterable `session_id` column). **OPEN PR: #206** (ADR-storage-010, FalkorDB native + the captained measurement). **DBs ARE a tracked deliverable** (team reviews stores via the inspector) — see [[checkpoint-git-hygiene]].
- **✅ FalkorDB captained measurement DONE (D059): native BEATS the in-memory baseline** on the convergent-hub divergence case (native solves gold@k=1, baseline misses; win provably structural). Run against a **real embedded FalkorDB** (`falkordblite`/`redislite`, py3.12 venv). **Capability proven; NOT a real-workload claim.** Artifacts: `work/falkor-measure/`.
- **⭐ SINGLE NEXT DECISION (in flight): how to deploy the graph backend in the plugin.** Wiring FalkorDB native into `build_store` is planned (`work/falkor-wiring/wiring-plan.md` — opt-in `fusion-falkor` profile, switchable, Keith's `contract.py` seam) BUT the **embedded `redislite` model spawns a redis-server subprocess with no `close()` chain → orphaned processes** (the fix = a cross-cutting close chain). **Researcher `researcher-qrp4` (codex) IS RUNNING** in worktree `amh-falkor-wiring`, evaluating: embedded-FalkorDB vs **external-Docker-FalkorDB** (Docker IS available — connect, don't spawn → likely avoids the orphan problem while KEEPING the built+measured native) vs **Neo4j** (external server, but native accuracy = the PARKED Phase B, unbuilt). **NEXT: read `researcher-qrp4`'s `output.md` → pick the deployment → then the wiring arc** (cross-team w/ Keith + a pipeline measurement run). Per [[ask-before-assuming-unavailable]]: Docker was wrongly assumed unavailable, which forced the embedded model.
- **Infra fixed today:** sandbox-login recurs as the token ages out (~8h) → **re-seed, don't `/login`**: `bash ~/projects/capstone-workspace/tools/reseed-sandbox.sh` ([[pipeline-sandbox-login]]). **Worktree layout** ([[branch-pipeline-runs]]): `agent-memory-harness` = pipeline runner (eval/pydata-xarray-pipeline, holds the 10G setup) + `amh-main` = main tracker. A **pipeline run is in flight** (builtin + plugin-blank @ `5ca7d7d` → another base-vs-memory data point when it lands; check `agent-memory-harness/results/`).

### Successor pointers (where things live — addresses the handoff reviewer's gaps)
- **PRD / SPEC / canonical architecture / implementation plan are NOT in this private workspace BY DESIGN** — they live in the SHARED repo `~/projects/agent-memory-harness` (+ its `docs/`, `docs/adrs/`). This workspace is Brent's private status/decision/evidence layer. A successor fetches the source brief + architecture from the shared repo, not here.
- **`researcher-qrp4` output (the graph-deployment decision input) is IN-FLIGHT** as of this handoff — lands at `~/projects/amh-falkor-wiring/work/agents/researcher-qrp4/researcher/output.md` (a shared-repo worktree, not this dir). It informs the deployment choice; the `work/falkor-wiring/wiring-plan.md` here is the FalkorDB-embedded wiring plan it may revise (toward external-Docker-FalkorDB).
- **In-flight pipeline run:** `~/projects/agent-memory-harness/results/vpydata_xarray_sequence-{builtin,plugin-blank}-5ca7d7d-1/` — DONE when `SUMMARY-swe_bench_cl-*.md` appears; another base-vs-memory data point.
- **Evidence-pack / presentation: KEN owns it now** (Brent reassigned 2026-06-26) — not Brent's slice to define. A backends-specific evidence file may come later, low priority. So the "undefined evidence-pack" is intentional, not a gap on this slice.

## CURRENT STATUS (2026-06-25) — read this first

### ⭐ BENCHMARK SEQUENCE = **xarray** now (sphinx + scikit ABANDONED — host-grader ceiling) (2026-06-25)
**The overnight `sphinx` BASE run graded 0/44 = a host-env GRADING ceiling, NOT P3 code / NOT a model result.** `SwebenchHostGrader` builds a host `uv` venv ≠ SWE-bench's conda base → most tasks UNGRADED ("official parser produced no statuses"). Diagnosed deterministically (gold patch, no LLM). `$0.00` cost is normal (subscription auth). After two abandoned sequences, **a full survey + empirical gold-patch test of all 8 sequences found the host-friendly ones — see memory `swebench-host-grader-env-ceiling` for the SEQUENCE MAP.**
- **✅ CHOSEN SEQUENCE: `pydata_xarray_sequence` (22 tasks, py3.10).** Gold patch grades **RESOLVED on current `main` with ZERO grader changes** — `needs_seed=False`, plain `pip install -e .`, plain pytest, no tox, no compiled deps.
- **Complete viability map (all 8 sequences gold-patch-tested; recorded in memory `swebench-host-grader-env-ceiling` + the team spreadsheet):** ONLY **xarray + sympy(50)** are RELIABLY gradeable (gold patch RESOLVES, zero grader changes). **django(50) + pytest(19) GRADE but false-negative the gold patch** (py3.6→3.8 substitution drift → untrustworthy numbers — worse than honest UNGRADED). **matplotlib/astropy/scikit/sphinx-4.x+ = "no statuses"** (C-extensions / old-py / tox / removed pip flags). → **sympy is the only solid additional sequence beyond xarray.**
- **⭐ STATUS: the full xarray run is DONE — HEADLINE RESULT IN (2026-06-25 PM, D053).** Both stages **fully graded (22/22, 0 ungraded)** on `claude-haiku-4-5` @ `6a0b0b4` — the host-grader ceiling is GONE on xarray, exactly as predicted: **base (memory OFF) 6/22 resolved (27.3%) → plugin-blank (memory ON, from empty) 7/22 (31.8%) = +1 task, +4.5pp accuracy, +0.039 efficiency.** plugin-blank memory health: 10 writes, 11 recall events, 7 recall hits, all durable. **Committed as durable shared-repo evidence — PR #177** (`eval/xarray-results-6a0b0b4`; via the `amh-xarray-results` worktree). **CAVEATS:** thin margin (+1 task on n=22, ONE full run each — no variance estimate); this is **plugin-BLANK** not plugin-accum (the pre-seeded "accumulated memory" hypothesis is UNRUN); it's **Haiku-vs-Haiku** (isolates the memory lift) not yet the PRD's Haiku-vs-Opus framing. **NEXT FORK (Brent's call):** STRENGTHEN (plugin-accum on xarray + sympy(50) for 4× n) vs BANK + pivot to backend upgrades (Voyage-rerank D046) / closeout.
- **Pipeline gotcha (LEARNED):** `make pipeline --stage` takes **ONE stage per invocation** (NOT `base,plugin-accum`). Run each as a SEPARATE invocation — `--stage base`, then `--stage plugin-blank` (or `plugin-accum`). `base` = memory OFF (writes NO memories, by design); plugin stages write to `results/v.../_memory/.cookbook-memory/`. Compare the two buckets' SUMMARYs manually (the old auto base→final delta is gone). Budget default **$10** (cost.py; too-low aborts mid-run; $0.00 cost reported is normal under subscription auth).
- **ABANDONED (host-grader rabbit holes, deadline):** **sphinx** — 3.x fixed (#167, shipped, stays merged/inert) but 4.x+ has a tox-current-env wall + Pygments drift (false-negatives); **scikit** — `--no-use-pep517` removed in modern pip + C-extension build + missing pytest. Both are eval-infra-grader limitations (Ken's domain), not worth the time.
- **#167 stays on `main`** (repo-scoped to sphinx, zero blast radius on xarray/others) — no revert.
- **Console:** cockpit live this session at http://127.0.0.1:45445/ (re-`agent-roster console --ensure --workspace <ws>` after a boundary; memory `reensure-console-after-boundary`).

### Shipped 2026-06-25 PM (after the overnight)
- **sphinx 3.x grader fix — PR #167 MERGED** (`6a0b0b4`): `uv venv --seed` + era-pins (`setuptools<60`/`docutils<0.16`) gated to `_CONDA_BASE_REPOS={sphinx}`; zero non-sphinx blast radius. (D048)
- **OKF frontmatter serializer — PR #171 MERGED** (`e2435ec`): type=content not provenance, first-sentence description, key-aware `x_metadata_json` dedup; `x_item_id` kept. Rich content (title/type/desc) = cross-team extractor follow-up (Scott + Keith). (D049/D050, `OKF_FRONTMATTER_TODO.md`)
- **Track D FTS5 lexical backend — PR #174 + #176 MERGED**: stdlib SQLite-FTS5 `Fts5Store`; **beats markdown lexical** (recall@10 0.842 vs 0.825, ~5× faster writes). (D051/D052)
- **MiniLM on the pipeline — fusion-local profile, PR #187 MERGED** (`stores/pipeline-local-ann`, `e052f21`; cc Keith; D055): opt-in `MEMORY_PROFILE=fusion-local` = fusion RRF + MiniLM/sqlite-vec, **no** SemanticRouterClassifier (the D046 winner; avoids D021's regression). Verified both paths (cache→MiniLM active; no-deps→clean hashing fallback) + a **preflight verifier** (`effective_profile.py`) that flags silent fallback. Offline (mixed, recall-positive): MiniLM recall@10 1.0 (vs 0.9966) but MRR 0.774 (vs 0.859); **semantic-divergence 0.80 vs hashing 0.00**. **MEASUREMENT PENDING** — but the **plugin venv IS NOW ENABLED** (`eval[local-ann]` installed into the repo-root `.venv` 2026-06-25; MiniLM loads cache-only; verified fusion-local→MiniLM active + the default hashing path non-breaking). So the measurement just needs **#187 merged → ff the pipeline branch → run** `MEMORY_PROFILE=fusion-local` (verify live with `effective_profile.py --require-local-ann` first). Full recipe in memory `fusion-local-minilm-enablement`. (D055)
- **FTS5 PRODUCTION SEAM — DONE, PR #183 MERGED** (`stores/fts5-build-store`; Keith green-lit the `contract.py` seam, D054): `build_store` now registers an `fts5` backend and the default **fusion profile fans out to it on the live plugin path**. Wired as a `base_all` **secondary index** (router.py `FTS5` const, gated on `FTS5 in self.backends`) — `write_base` stays MARKDOWN (D001 source-of-truth); fts5-less routers byte-identical. **Eval: `fusion_rrf_with_fts5` holds recall@10 0.9966 + improves MRR@10 0.864 vs 0.859** (no dilution; no-regression asserted). Cross-vendor gated PASS (codex build → claude verify, 8/8). **Caught + reverted a deviation:** the implementer's `write_base="fts5"` (would mislabel the source-of-truth + drop markdown under `base_selective`). Note: `speed_profile` (base_all) also writes fts5 (doesn't fuse on read) — harmless. So D044's "production seam DEFERRED" is now CLOSED for FTS5.
- **Worktrees:** main = the running **xarray pipeline** (`eval/pydata-xarray-pipeline`); `amh-okf-frontmatter` (OKF, merged — removable); `amh-track-d-fts5` (FTS5 PR #174). Backend/tooling dev runs in worktrees so the live pipeline tree is never edited mid-run.
- **Benchmark menu now:** ~~Track D FTS5~~ ✅ #174/#183 · captained Voyage-rerank-on-MiniLM-fusion (D046 next) · Track B FalkorDB (D044) · Track E learned router · 10k throughput · bge-m3.

### Session-continued (2026-06-25 eve) — ⭐ SINGLE NEXT TASK + open threads
**✅ DONE (2026-06-26, D057): the xarray accum run landed — memory +1 task AGAIN.** At SHA `72d00a7`: **`builtin` (no memory) 5/22 → `plugin-accum` (seeded memory) 6/22 = +1 task, +4.5pp**, both 22/22 graded clean. Memory genuinely engaged (stage-level recall_attempted=22, recall_with_hits=22; builtin=0). Second independent +1 (mirrors the banked 6a0b0b4 base 6→plugin-blank 7). **Banked scrubbed → PR #196 MERGED** (text) **+ PR #199 MERGED** (the `memory.db`/`graph.db`/`fts5.db` stores — the team reviews each other's stores via the inspector, so DBs ARE a tracked deliverable; they carry Brent's host path in one daydream memory's content, accepted as non-sensitive — no creds; see [[checkpoint-git-hygiene]]). **CAVEATS:** n=22 single runs, no variance; the accumulation hypothesis is NOT separately proven (seeded accum 6 ≯ blank plugin-blank 7, but different SHAs). **Reporting bug FILED** (TEAM_NOTES #3, cc Ken/Keith): the SUMMARY "Memory health" table shows recall_events=0 for plugin-accum, contradicting stage-level recall_attempted=22 — a summary-tooling aggregation bug, not a memory-off run. *(The dim-mismatch heads-up didn't bite: the run used plain hashing, matching the seed.)*
**⭐ NEXT:** FalkorDB **PR2** (native typed-graph + captained measurement) in design (`architect-567f`); + the deferred menu (Voyage-rerank D046, capstone evidence-pack ~4-day deadline still UNDEFINED).
- **PR #189 MERGED — ui inspector offline-browse fix** (`fix/ui-inspector-offline-browse`, cc Ken): `make ui` left the inspector empty — it loads `.env`, saw `VOYAGE_API_KEY`, auto-picked `accuracy`, and re-embedded graph nodes via the Voyage *network* on open → 3s timeout. Fixed: default `--profile fusion` (offline browse; real embedder opt-in for query-probe). Until merged, browse with `make ui ARGS="--profile fusion"`. 31 ui tests pass.
- **Sandbox login FIXED** — `eval/.claude-sandbox` OAuth was empty (Brent's `open-*` .bashrc funcs export OpenRouter `ANTHROPIC_BASE_URL`/`AUTH_TOKEN`/`API_KEY` → sandbox `/login` ran in API-key mode). Seeded from the valid host cred. **Run pipelines from a `claude-reset`'d shell** (runtime strips AUTH vars but NOT BASE_URL). Memory `pipeline-sandbox-login`.
- **plugin-blank-6a0b0b4-3 store RESTORED** — its `memory.db`/`graph.db` got deleted in a results cleanup; restored from `e080b92`. **Lesson:** clean aborted runs SUMMARY-aware; NEVER blanket `git clean -fdx results/` (it nukes completed runs' gitignored DBs while the tracked md files survive, so the dir looks present but the UI reads 0). Memory `dont-blanket-clean-results`.
- **⭐ LIVE RUN SHAPE (2026-06-26, observed at /pickup):** the restarted run is at SHA **`72d00a7`** (NOT the banked `6a0b0b4`) with two stages: **`plugin-accum`** + **`builtin`** (NOT `base`). Both IN FLIGHT (no `SUMMARY-*` yet; JSONs updating live). So the clean comparison when it lands is **builtin vs plugin-accum @ 72d00a7** — a direct compare to the banked **base 6/22 @ 6a0b0b4** is NOT apples-to-apples (different code SHA).
- **Track B — FalkorDB graph backend (D044, D056, D058):** **PR1 MERGED (#193)** = the offline **parity FLOOR** (FalkorDB Redis/openCypher sibling of `Neo4jGraphStore`, parity-by-construction, MATCH-never-MERGE, lazy/fail-loud). **PR2 native mechanism → PR #200 OPEN** (`stores/falkor-native`, cherry-picked clean onto main): opt-in `native=True` typed-graph materialize + variable-length traversal + importance-weighted multi-path accumulation scorer; default stays the parity floor byte-for-byte (28 parity tests). FalkorDB Cypher surface web-verified (3 corrections: no IF-NOT-EXISTS, client-side seed fold, no algo.* dependency). 5 structural + offline divergence-headroom tests; full stores suite 443/0-fail. Both PRs MERGED (#193, #200). **✅ CAPTAINED MEASUREMENT DONE (D059): native BEATS the in-memory baseline** on the convergent-hub divergence case (native solves gold@k=1, baseline misses; win is provably structural via link-differential) — run against a real embedded FalkorDB (`falkordblite`/`redislite`, py3.12 venv, NO Docker). **Capability proven; NOT yet a real-workload claim.** **⭐ NEXT (open): wire `native=True` into the live plugin path** (`contract.build_store` graph profile, Keith's seam) + a pipeline run to measure on the actual SWE-Bench-CL/xarray benchmark; + write ADR-storage-0NN. See `GRAPH_STORE_SCOPE.md` + D056/D058/D059; artifacts in `work/falkor-measure/`.
- **Queued (Brent's call):** fusion-local measurement (venv ready; run `MEMORY_PROFILE=fusion-local` after verifying with `effective_profile.py --require-local-ann`) · **capstone evidence-pack** (deadline ~4 days, still UNDEFINED — getting time-sensitive) · captained Voyage-rerank (D046).
- **Open PRs:** none — **#187 (fusion-local + verifier) and #189 (ui fix) both MERGED.** **Worktrees:** `amh-pipeline-local-ann` (#187), `amh-ui-fix` (#189), `amh-fts5-buildstore` (#183) all merged — removable. Main checkout = Brent's sacred pipeline runner.

### Landed 2026-06-24 (Brent's slice) — all MERGED to shared `main`
- **Track C** (local MiniLM + sqlite-vec ANN) — **PR #151 MERGED**.
- **router_ui inspector → upstreamed to the shared repo** — **PR #156 MERGED** (`agent-memory-harness/router_ui/`, run `./router_ui/run.sh`); the capstone copy is RETIRED.
- **`.env.example` Router section** (profile precedence + `MEMEVAL_LOCAL_ANN` + `MEMEVAL_ALLOW_MODEL_DOWNLOAD`) — **PR #155 MERGED** (the teammate MiniLM how-to).
- **Inspector `accuracy-local` profile + the `.env`-loading fix** — **PR #160 MERGED** (`main` @ `54d168e`; the inspector now `load_root_dotenv()`s so its profile field reads `.env`, and supports `--profile accuracy-local`).

---
**✅ MERGED to `main` (2026-06-24 night):** Track 0 + Track A are LANDED.
- **PR #138** (`stores/track0-scale-eval`) — Track 0 scale-retrieval benchmark — **MERGED to `main`** (squash `714923f`). Carried Track A too + the CodeRabbit `skip.name` NameError fix (`helpers.py:550`).
- **PR #139** (`stores/track-a-fusion-rerank`) — Track A rerank-in-`RouterConfig` — **MERGED** into the Track-0 branch first, so #138 landed both.
- `main` is now **`7e2fa69`** (Scott's dreaming instrumentation #137 stacked cleanly on top; `714923f` intact, no storage/router overlap). 351 stores-tests green; cross-vendor verified. *(The older local `stores/backend-upgrades` arc branch with the parked semantic/minilm bake-off was NOT pushed; these tracks were rebased OFF it onto `main` for clean PRs.)*

**✅ MERGED — Track C (real local embeddings + ANN) = PR #151 (squash-merged to `main`):** was branch `stores/track-c-embeddings-ann` @ `e7826ad`. `SentenceTransformersEmbedder` (all-MiniLM-L6-v2, 384d, lazy/CPU/local_files_only, hashing fallback) + `SqliteVectorStore(vector_index="sqlite_vec")` (sqlite-vec vec0 ANN, over-fetch(50)+exact cosine rerank, generation-counter coherence, brute-force fallback) + `router.accuracy_local_profile()`, all **OPT-IN** (`MEMEVAL_LOCAL_ANN=1`); the stdlib hashing brute-force path stays the deterministic CI floor (offline default byte-equivalent). **Eval (D046, captained deps-present A/B):** `fusion_local_ann` recall@10 **0.981 vs hashing 0.919** — gain entirely semantic (0.167→0.800), no regression, ~3.6× faster. **Gate:** offline floor 364 OK/11 skip + 98 smoke; cross-vendor (build-time claude verifier caught+fixed an ambiguous-column ANN-SQL bug; pre-push codex verifier-7pb6 PASS). **`contract.py` decision (D047):** the `accuracy-local` live-path selector edits Keith's `build_store` seam — Brent chose KEEP-IN-PR + **cc @kmazanec** flag (additive only; existing accuracy/fusion/speed selection unchanged). Open teammate PRs: **#140 MERGED** (Keith grader fix, in `origin/main`) · **#137 MERGED** (Scott dreaming). **NOTE: the headline 0.981/0.919 numbers are NOT in a committed CI artifact** (deps-absent floor can't reproduce them) — reproduce with the `[local-ann]` extra + `MEMEVAL_LOCAL_ANN=1`; an optional follow-up is to commit a deps-present result JSON as tracked evidence.

**Shipped the build day (2026-06-24):**
- **Track 0 — Scale Retrieval Benchmark (PR #138):** a deterministic, offline, CI-safe eval exercising the stores+router at realistic memory volume — **the fast inner-loop every backend upgrade now ships against** (`make pipeline` stays the final arbiter). 5-lens calibrated corpus (1.5k quality → 291 retained); a **target-must-beat-floor** anti-theater calibration gate; config matrix with `Skip`-reserved ANN/native-graph/FTS5/Voyage columns; committed offline matrix; 6-test smoke; reproducible from committed fixtures (filler=100). Lives in `eval/memeval/stores/tests/scale_retrieval/`. Headline (offline/hashing): **graph_bfs recall@10 1.000 / fusion_rrf 0.997 dominate route_speed 0.876.**
- **Track A — rerank-in-the-router (PR #139, D045):** `RouterConfig.reranker`/`rerank_top_n`; `Router.route()` wraps its base retriever in a `RerankedStore` when the profile sets a reranker; `fusion_profile()`/`accuracy_profile()` carry it; the build-layer `build_router_store` helper was REMOVED (reranking is the router's domain, the same layer as fusion). **Findings:** route-to-one throws away relational recall (multi_hop **0.348 → 0.978** under fusion); the **captained** Voyage rerank takes semantic-divergence **MRR 0.922 → 1.000** (recall saturated). Verdict: **fuse-all + rerank is the best retrieval config.**
- (Earlier this session: the `router_ui` inspector + the **semantic-routing-deferred** finding still stand — see DECISION_LOG.)

**⭐ The headline `make pipeline` gate — RE-VALIDATE before running:** the #136 grader fix (`452102d`) that lifted Brent's go-signal is now buried — `origin/main` has advanced to **`44648e4`**, and the benchmark **surface itself changed**: **#141 + #146 added VISTA as a 2nd benchmark ("two-benchmark refocus") + an RSI safety gate + native-metric reporting**, plus #140 (another grader fix) and dreaming diagnostics #142–#145. So before spending budget, **re-confirm the go-signal against the NEW two-benchmark surface** (the run is intentionally gated on Brent's word). The pipeline is still the only metric that decides anything.

**Cross-team hand-off READY:** making **fuse-all + rerank the LIVE default** is now a **one-line PROFILE change** in `plugin/cookbook_memory/core/contract.py::build_store` (Keith's seam) — point the keyed/accuracy path at a fusion + `VoyageReranker` profile; NO reranker wiring in the plugin (rerank rides in the profile). Track A shipped the composition + the evidence.

**↳ TOP NEXT MOVE (2026-06-25 PM — SUPERSEDED, see the ⭐ CURRENT STATUS block at the top):** the overnight sphinx run was diagnosed (host-grader ceiling) and the benchmark pivoted to **xarray** (full run IN FLIGHT in Brent's terminal). Read its result + the base-vs-plugin delta when it lands; **sympy(50)** is the only solid additional sequence. The pipeline is the ONLY metric that decides anything.

**The build menu (Brent's call, all eval-first against the Track 0 scale benchmark):** ~~Track C real embeddings + ANN~~ ✅ **SHIPPED = PR #151** · ~~Track D FTS5 lexical~~ ✅ **SHIPPED = PR #174 (D051)** · captained Voyage-rerank-on-MiniLM-fusion (D046 next) · Track B native graph (FalkorDB / Neo4j Phase-B) · Track E learned router · the **captained Voyage matrix** (spend gate) · the **Keith hand-off** · the **pipeline run** (re-validate go-signal vs the VISTA two-benchmark surface first) · ~~close out the router_ui badge work~~ ✅ **DONE** — the badge drill-in was first committed (`bd051f3`), then **replaced** (Brent's spec) by a **backend-artifact popover** (`36d6b9e`): clicking a memory's md/vec/graph badge shows that backend's STORED ARTIFACT (md = the real OKF `.md` file + frontmatter; vec/graph = stored record + edges) with a **Copy-path** button (per-memory `.md` for md; shared `memory.db`/`graph.db` for vec/graph). `substrate.artifact_view` + `GET /api/backend-artifact`; reuses the shared modal; 22 tests; codex verifier-4zrw PASS (after a doc-truthfulness fix). *(Note: only static assets hot-reload — editing `router_ui/server.py` requires a server restart.)* **↳ UPSTREAMED 2026-06-24: router_ui now lives in the SHARED repo (`agent-memory-harness/router_ui/`, PR #156) + its env knobs are documented there (PR #155); the capstone copy is RETIRED. Subsequent inspector work happens in the shared repo, not here.**

**Pipeline how-to:** `cd agent-memory-harness && make setup` once; the run drives the `claude` CLI against an isolated `eval/.claude-sandbox` (one-time `/login`); always pass a small `--budget-usd`; keys in `agent-memory-harness/.env` (**authoritative**; a `capstone-workspace/.env` mirror exists). Captained OFFLINE evals (e.g. the Voyage rerank A/B `work/track_a/voyage_rerank_semantic.py`) just need `MEMEVAL_LIVE=1 VOYAGE_API_KEY=…` — no sandbox login. **Known-open (NOT blockers):** the eval-harness `MemoryFramework.{write,get,search,all}` stubs stay bypassed by `build_store` (wire-or-retire, undecided); the capstone evidence/closeout artifact is not defined yet.

## Workspace split (important)
- **`~/projects/agent-memory-harness`** — the SHARED code repo. Brent's real deliverables live
  here; changes ship via small PRs on `stores/*` / `router/*` branches.
- **`~/projects/capstone-workspace`** (this dir) — Brent's PRIVATE planning/evidence/scratch,
  NOT in the shared repo. Holds: this `CONTEXT.md`, `DECISION_LOG.md` (D001–D044, the AI
  suggested/accepted/changed/rejected log), `ROUTING_EVALS.md`, `TEAM_NOTES.md`, and `work/` (gitignored
  scratch: delegate run dirs + throwaway eval scripts). The agent file-memory (`memory/` + `MEMORY.md`)
  lives separately under `~/.claude/projects/-home-brent-gibson-projects-capstone-workspace/memory/`
  (auto-loaded each session), NOT in this dir. Demo/info material made here may target **Nerdy**
  (tentative — not folded into any plan yet).
- **Vendored tooling — the `/kb` slash command (a PRIVATE FORK):** `.claude/commands/kb.md` is copied
  from the shared repo (agent-memory-harness PR #71, Scott) so KB project-story entries can be drafted
  here (in **storage** domain) without working in the project repo, then synced upstream. It hard-requires
  `docs/adrs/README.md` (a LOCAL MIRROR of the project's ADR domain taxonomy — not canonical; the real
  ADRs live in `~/projects/agent-memory-harness/docs/adrs/`). Run here, `/kb` sources from
  CONTEXT/DECISION_LOG/commits and writes append-only to `.kb/KB-<domain>.md`. **Sync discipline (drift
  points):** (1) re-copy `kb.md` if Scott updates upstream; (2) keep `docs/adrs/README.md`'s domain table
  in sync with the project's (the four domains harness/storage/dreaming/eval — `/kb` STOPS if they drift);
  (3) copy `.kb/` entries generated here into the project's `.kb/KB-storage.md` when ready to share. New
  project slash commands appear only after a session restart (discovered at session start).

## Current state: core build SHIPPED; routing+embedder slice + write-path arc COMPLETE & MERGED; routed writes LIVE on the product path via RouterStore (#76); the **full solo graph thread is DONE** (Neo4j Phase-A #111) and the **Backend Durability Hardening Arc shipped & MERGED** (#117, squash `9d77ecb`); a research+architecture-reconcile Workflow produced 7 storage ADRs (#118, MERGED, squash `6b03d32`) + parked Neo4j Phase B; **headline remaining gate = the captained benchmark metric run** (see Active work) *(SUPERSEDED — see "CURRENT STATUS (2026-06-24)" at the top for live status + the single next task.)*
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

## Active work: routing+embedder slice + write-path arc COMPLETE & MERGED; write-routing LIVE on the product path via RouterStore (#76); the graph arc is FULLY DONE (durability→delete→e2e #92/#93/#95/#99/#101 MERGED + Neo4j Phase-A #111 MERGED); the **Backend Durability Hardening Arc shipped & MERGED (#117, squash `9d77ecb`)** + a research/architecture-reconcile Workflow shipped 7 storage ADRs (#118, MERGED, squash `6b03d32`) and parked Neo4j Phase B; **next = the captained benchmark run (the headline gate)** (updated 2026-06-23) *(SUPERSEDED — see "CURRENT STATUS (2026-06-24)" at the top for live status + the single next task.)*
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
- **Semantic retrieval eval (per D019) — MERGED as PR #44** (`stores/d019-semantic-retrieval-eval`):
  `test_semantic_retrieval_evals.py` — 20 cases (15 semantic-divergence across synonym/paraphrase/
  conceptual/cross-lingual/abstraction lenses + 5 lexical controls) over a 34-memory haystack. The
  committed offline path proves **headroom, not victory**: divergence recall@5 **0.000** (hashing
  misses gold in top-k), control recall@5 **1.000** (apparatus works) — both machine-asserted against
  the real hashing path (anti-theater). Provenance: blind multi-lens Workflow → synthesizer → per-case
  verify → deterministic offline calibration (dropped 12/27 generated divergence cases the hashing
  embedder could already find). stdlib-only; no production code. Cross-vendor Codex gate PASS (concerns
  remediated). The live hashing-vs-Voyage **measurement was captained (D020, DONE — see next bullet)** —
  never in CI (offline guarantee). Finding: cross-lingual + conceptual queries defeat lexical matching
  reliably; synonyms barely do (shared morphology).
- **Captained D020 live run — DONE (DECISION_LOG D020):** ran hashing FLOOR vs real `voyage-3-large`
  (dim 1024, doc/query asymmetry) over the new semantic fixture. **Result: divergence recall@5
  0.000 → 1.000 (15/15 recovered), MRR 0.000 → 0.922; control 1.000 → 1.000 (no regression); all 5
  cross-lingual recovered to rank 0.** The complete inverse of D019's lexical-fixture result — the
  embedder's value was real all along; D019's fixture hid it. Voyage's benefit is now demonstrated on
  an instrument whose cases are machine-proven beyond a lexical retriever. (Script: `work/voyage_semantic_eval_d020.py`.)
- **PR3b-2 (`SemanticRouterClassifier`) — MERGED as PR #49** (`router/pr3b2-semantic-classifier`):
  exemplar-NN learned classifier in `router.py` behind the existing seam (D016 accuracy profile) — embeds
  per-backend GENERIC exemplars + the query with an injected encoder (e.g. `VoyageEmbedder`), routes to the
  nearest region by cosine (margin + nearest-exemplar in `details`). No `[CONTRACT]` change; default/speed
  (rule) path untouched; encoder injected (offline guarantee). Exemplars blind-generated, non-project,
  de-leaked (cross-lingual French-GAP near-copy + an English eval near-dup). `test_semantic_classifier.py`
  (12 CI-safe tests): deterministic mechanism (routing, doc/query asymmetry, empty-default, protocol fit,
  with_config, tie-break, legacy encoder) + offline-seam smoke. Asserts MECHANISM only — semantic accuracy
  is the captained D021 run. Cross-vendor Codex gate PASS. The bake-off harness is intentionally unchanged.
  **D021 verdict: ships as an accuracy-profile STRATEGY, NOT adopted standalone (see below).**
- **Captained D021 live bake-off — DONE (DECISION_LOG D021):** `SemanticRouterClassifier` (real
  `voyage-3-large`) vs rules over the 73-case routing eval via the committed `score_strategy`/`eligibility`.
  **Result (rules → semantic): BLIND-hard 28/31 → 19/31 (−10), AGREE 24/24 → 17/24, golden 12/12 → 8/12,
  GAP:multilingual 0/3 → 2/3 (recovered de + zh depends-on; missed fr conflict), net delta −14 → NOT
  eligible.** It generalizes cross-lingually (real, since exemplars are generic + de-leaked) but coarse
  nearest-exemplar matching loses the rules' precise lexical signals and regresses English. The **eval-first
  bar (recovery AND no-regression) correctly rejected it** as a drop-in rules replacement — the failure an
  "it does multilingual!" demo would have hidden. (Script: `work/voyage_routing_bakeoff_d021.py`.)
- **Rules→semantic HYBRID — SCOPED OUT (DECISION_LOG D022).** Eval-first grounding *before* building
  killed it: the multilingual GAP cases are NOT no-signal — their code identifiers (`RouterConfig`/
  `embedding_store`/`rate_limiter`) fire a confident-but-wrong markdown token (best 1.0/2.5/2.0),
  score-indistinguishable from correct English markdown (golden 1.0–3.0). No rules-confidence threshold
  separates them; the only separator is language, and blanket semantic-override regresses English (D021).
  Decision: multilingual routing is a **known limitation** for the **learned north-star router (D007)**;
  rejected a brittle language-gate (the fr case has no accents) and overfit multilingual rules. The
  **routing + embedder slice (D008–D022) is COMPLETE & measured.**
- **WRITE-PATH ARC — re-opened (Brent: "accurate on writes AND retrievals").** A sanity audit
  (`REMEDIATION_PLAN.md`, 27 items / 7 high) found the read side solid but the write side underbuilt.
  Sequence (eval-first, each its own gated PR):
  - **Step 1 — WAL: DONE.** `SqliteVectorStore` opens with `PRAGMA journal_mode=WAL` (ADR-P2) — **#52
    merged**; CodeRabbit enforcement follow-up **#55 MERGED** (raise if a file-backed DB didn't get WAL).
  - **Step 2 — write-routing (D023): MERGED as PR #56.** `Router.route_write(item)` (the router
    owns WHERE to STORE, D009); default `write_policy=base_all` chosen by a round-trip calibration
    (1.000 vs selective 0.708 — content/query classification diverge under the rule classifier). Offline
    eval; cross-vendor Codex gate PASS. `route_write` is the router side; the agent/MemoryFramework
    *calling* it is cross-team (Keith).
  - **Step 3a — dedup-on-write (D024): MERGED as PR #57.** `Router.write(item) → WriteReceipt`
    (dedup-resolve → route_write → persist; newer-content-wins, version+1). **Default OFF** — D024
    calibration proved offline lexical similarity can't separate near-dups (0.35–0.75) from
    distinct-but-similar memories (0.21–0.82; a distinct "read 5s" vs "write 30s" scores 0.824 > every
    real dup), so auto-merging would FALSE-MERGE = silent data loss; gated to a real embedder. Codex
    gate PASS. Mechanism built + validated; the eval machine-checks the overlap + demonstrates the danger.
  - **Step 3b — version-highest-wins: CROSS-TEAM (deferred).** Per-store vs dreaming-layer ownership is
    an open team question (TEAM_NOTES#1; Brent's lean: dreaming/persistence concern) — not a solo build.
- **SOLO write-path work DONE** (WAL ✓ #52/#55, write-routing ✓ #56, dedup ✓ #57) + **RouterStore adapter ✓ #66 (D025, merged)** — and the live plugin **now consumes it** (#76/ADR-harness-011, verified in code): `_Engine.remember` → `store.write` (routed + deduped) via `contract.build_store` → `RouterStore`; dreaming too (#79). So routed writes are **LIVE on the product path**, not just injectable. (The eval-harness `MemoryFramework` stubs are bypassed by `build_store` — decide wire-or-retire.) Remaining = a captained benchmark metric run.
- **WHERE STORAGE ACTUALLY LIVES (UPDATED 2026-06-23, #76/ADR-harness-011 + Keith's graph-path wiring — verified in code):** the plugin is a
  **dumb client of `contract.build_store(store_path)`**, which returns ONE opaque `MemoryStore` = a **`RouterStore` over
  `Router.with_config(backends, config)`** and owns all assembly. The 3 backends build under `$MEMORY_STORE` (config.py:46;
  plugin hooks set it to **`${CLAUDE_PROJECT_DIR}/.cookbook-memory`**): **vectors → `$MEMORY_STORE/memory.db`** (SQLite file),
  **markdown → `$MEMORY_STORE/markdown/`** (OKF docs), **graph → `$MEMORY_STORE/graph.db` (NOW PERSISTED — Keith wired
  `contract.py:100` to `GraphStore(path=str(root / "graph.db"))` THIS session, consuming the #92/D035 `path=` seam; verified
  end-to-end: `build_store` creates `graph.db`, a fresh store reloads nodes after restart, a typed edge survives — the durability
  gap is CLOSED on the live path)**, events → `$MEMORY_STORE/<events>.jsonl`. The engine **auto-selects the profile** with zero plugin
  input: `$MEMORY_PROFILE` forces speed/fusion/accuracy; else `VOYAGE_API_KEY` present → **accuracy** (semantic classifier +
  Voyage embedder + cascade); else → **fusion** (offline RRF); speed is never auto-selected. **BOTH reads AND writes now go
  through the router:** `recall()` → `store.search`; `remember()` → `store.write` (routed + deduped via `Router.write` — the
  old markdown-hardcode is GONE). Dreaming writes route through the same `build_store` (#79). **Still a stub:** the
  eval-harness `MemoryFramework.{write,get,search,all}` (`opencode/framework.py:60-77`) remains `NotImplementedError`, but
  the live plugin/bench path BYPASSES it (uses `build_store`) → a decide-wire-or-retire, not a live blocker.
- **⭐ TOP PRIORITY (UPDATED 2026-06-22) — RouterStore is now ADOPTED on the live plugin path; the remaining gate is the
  captained benchmark run.** `RouterStore` (#66, D025) made the Router's routed+dedup write path a drop-in `MemoryStore`;
  the plugin was then refactored to consume it (**#76 / ADR-harness-011, verified in code**): `_Engine.remember` →
  `store.write` (routed + deduped; markdown-hardcode GONE) and dreaming (#79) both route through `contract.build_store` →
  `RouterStore`. So **write-routing + dedup are LIVE on the product path.** What actually remains: (a) a **captained**
  large-benchmark metric run (real embedder; auto-accuracy-profile when `VOYAGE_API_KEY` is set) to show the lift over
  `InMemoryStore` — the headline-metrics gate (offline samples show parity, D019/D020 lesson); (b) the eval-harness
  `MemoryFramework.{write,get,search,all}` stubs (`eval/memeval/opencode/framework.py:60-77`) are still
  `NotImplementedError` but the live path BYPASSES them → decide wire-or-retire (not a blocker); (c) version-highest-wins
  ownership (cross-team).
- **THEN (menu):** the **full solo graph thread is DONE** (accuracy + durability + delete #75–#101, D029–D038; **Neo4j
  Phase-A parity floor #111, D041**) and the **Backend Durability Hardening Arc shipped & MERGED (#117, D042, squash `9d77ecb`)**. **Newly NEXT:**
  with **#117** (hardening) + **#118** (7 storage ADRs, D043, squash `6b03d32`) both MERGED, the **captained large-benchmark run is the
  headline metrics gate**. Queued solo/captained: the **captained live `NEO4J_TEST_URI` run** (HARD prereq for Phase B) →
  **Neo4j Phase B** (native typed graph from `okf_links` + GDS/Cypher, D043 PARKED) + the deferred hardening follow-ups
  (GraphStore cross-process read freshness — a pre-existing residual, not a regression — + the markdown MEDs). **Keith's plugin
  `build_store` graph-path wiring — ✅ DONE this session (`contract.py:100` → `GraphStore(path=…/graph.db)`; the live plugin graph
  is now durable, verified end-to-end).** Cross-team remaining: architecture.md reconciliation (`docs/architecture-reconcile`,
  local — a `[CONTRACT]` team-meeting call). Other backlog: 17 contested labels; perf-testing; bge-m3 must-have-vs-descope;
  capstone closeout/evidence-pack.
- **Resume:** shared `main` @ current (teammate PRs merged since: #60 dataset schema, **#61 PRD-compliance
  audit + ablation survey**, **#62 Docker removed / Claude Code CLI coding agent**, **#63 benchmark-native eval
  pipeline (5 benches)**, #64 stores docstring, #65 CC rationale, **#79 dreaming routes writes through Router, #80 code-agent retry**, **#114/#115 pipeline/dream-stage harness wiring**). `main` synced through **#111** (the graph durability→delete→e2e arc + the delete `[CONTRACT]` + **Neo4j Phase-A** all merged) — and since **advanced to `b7d16d0`** (see the merge note below). Write-path arc **#52/#55/#56/#57 MERGED**;
  **RouterStore #66 (D025, MERGED)** + the plugin **consumes it on the live path (#76/ADR-harness-011, verified):** `_Engine.remember` → `store.write` (routed + deduped) via `contract.build_store` → `RouterStore`; dreaming too (#79). So routed writes are **LIVE on the product path** (not just injectable); the harness `MemoryFramework` stubs are bypassed by `build_store` (decide wire-or-retire).
  **MERGED: PR #117** (Backend Durability Hardening Arc, D042, squash `9d77ecb`) + **PR #118** (7 storage ADRs ADR-storage-003..009, D043, squash `6b03d32`) — both ancestors of origin/main. **`main` now at `b7d16d0`**, which also pulled in teammates' **#116** (dreaming deepseek test + ADR-dreaming-022), **#119** (plugin recall permissions + write counts), **#120** (commit-scoped pipeline memory). **LOCAL/unpushed:** `docs/architecture-reconcile` (01562b3, D043 — architecture.md drift reconcile; `[CONTRACT]`, a team-meeting governance call).
  **THE SOLO GRAPH THREAD IS FULLY DONE** (#75–#101 + **Neo4j Phase-A #111/D041**). **THE DURABILITY ARC SHIPPED** (#117/D042): markdown/OKF made production-durable (atomic write + cross-process flock + persisted generation-counter w/ reconcile-under-lock + O(1) delete + corrupt-file guard), sqlite/graph thread-safe; `test_backend_durability.py` (16); gate Codex R1 FAIL→R2 FAIL→R3 PASS + CodeRabbit fold.
  **Next-session priorities: (1) #117 + #118 are MERGED** (squash `9d77ecb` / `6b03d32`; both ancestors of origin/main — the merge precondition is met). **(2) ⭐ the captained large-benchmark metric run** (real embedder; auto-accuracy-profile when `VOYAGE_API_KEY` is set) — **the single headline-metrics gate** now that the build line is clean (Haiku+harness beats Opus-no-memory on ≥2/5 benches; team-level — Brent contributes the per-store inputs). **(3) deferred hardening follow-ups** (GraphStore cross-process read freshness — same generation-counter class, a **pre-existing residual, NOT a regression**; + the markdown MEDs: slug-collision hashing, type-change orphan-resurrection-on-write, persisted/lazy index). **(4) the captained live `NEO4J_TEST_URI` run** (validates Phase-A Cypher vs real Neo4j 5.x — flips the live test's captained-pending flag; **HARD prereq for Phase B**; Brent's, needs a DB). **(5) Neo4j Phase B** (D043, PARKED — a `native=True` mode INSIDE `Neo4jGraphStore`: materialize the native `[:REL]` graph from the `okf_links` SSOT, `MATCH` endpoints / never `MERGE`, native Cypher/GDS; the transient-delegation path stays the default+baseline). **Keith's plugin `build_store` graph-path wiring — ✅ DONE this session** (`contract.py:100` → `GraphStore(path=…/graph.db)`; all 3 backends now persist under `$MEMORY_STORE` on the LIVE path — graph durability verified end-to-end). Cross-team remaining: the architecture.md reconciliation → team meeting → push/merge (`GRAPH_STORE_SCOPE.md` Phase B + `docs/architecture-reconcile`). FalkorDB is REOPENED as a candidate graph backend (D044, pending eval) — design risks (re-introduces D041's bugs if naive → MATCH-never-MERGE; separate Redis client / new backend; preserve the stdlib test floor), not vetoes.**
  See `REMEDIATION_PLAN.md` for the full backlog.

## How to verify (run from `~/projects/agent-memory-harness/eval`)
- Smoke gate (the team's CI check): `python3 tests/test_smoke.py` → **95 passed / 1 skipped (96 collected), 0 failed** as of 2026-06-23 on `b7d16d0` (the contract is **0 failed**; the absolute count drifts as `main` moves — it was 97 earlier this session, then 95 after teammate merges; was 67→71→73→82→95→97→95). Brent's full stores suite: `python3 -m unittest discover -s memeval/stores/tests -p 'test_*.py'` → **337 passed / 3 skipped (340 collected)** (the 3 skips are intentional env-gated — live Voyage `MEMEVAL_LIVE`/`VOYAGE_API_KEY` + live Neo4j `NEO4J_TEST_URI` — not failures). New suites this session: `test_backend_durability` (16), `test_neo4j_parity` (28), `test_neo4j_live_parity` (opt-in, `@skipUnless NEO4J_TEST_URI`).
- D008 retrieval/gate fixture: `python3 -m memeval.stores.tests.test_d008_evals` (report) · `... -m unittest ...` (now on `main`). Cascade tests: `test_d008_cascade`; profile matrix: `test_profile_matrix`; bake-off: `test_routing_bakeoff`; Voyage embedder: `test_embedders`; semantic retrieval (PR #44, merged): `test_semantic_retrieval_evals` (report: divergence recall@5 0.000 / control 1.000); write-routing: `test_write_routing_evals`; dedup: `test_dedup_evals`.
- Brent's suites: `python3 -m unittest memeval.stores.tests.test_markdown_store memeval.stores.tests.test_sqlite_store memeval.stores.tests.test_graph_store memeval.stores.tests.test_router memeval.stores.tests.test_routing_evals`
- Reproduce the routing number: `python3 -m memeval.stores.tests.test_routing_evals` → **28/31 = 90%** agreement on the blind hard cases.
- Env: `python3` + `uv` (no `python`/`pip` on PATH). The offline path is zero-dependency.

## What's next (see Active work above for the live build state + the single next task)
1. **Routing + embedder slice (D008–D022)** — *COMPLETE & measured* (PR1 #17 → PR3b-1 #41 → semantic-retrieval eval #44 → PR3b-2 #49, all merged; D020 recall@5 0.000 → 1.000; D021/D022 semantic classifier bounded). **Write-path arc (re-opened, D023/D024)** — *SOLO WORK DONE & MERGED*: WAL (#52/#55) → write-routing (#56, D023, default base_all) → dedup-on-write (#57, D024, default OFF/real-embedder-gated) — all in `main`. Since then: RouterStore (#66/D025), reranker (#67/D026), fusion profile + bake-off (#68/#72/D027/D028), graph eval Step 0 (#75/D029), graph Step 1 typed/directional (#81/D030), graph Step 1b `okf.py` anchor-capture (#84/D031), graph multi_hop configurable `max_depth` (#85/D032), graph accuracy-profile depth wiring (#86/D033), semantic_seed (#89/D034), graph durability (#92/D035), delete (#93/D036), e2e CRUD (#95/D037), delete `[CONTRACT]` on the protocol (#99+#101/D038), **Neo4j Phase-A parity floor (#111/D041 — the last solo graph thread, DONE)** — all merged. **This session (2026-06-23): the Backend Durability Hardening Arc (#117/D042, MERGED, squash `9d77ecb`) + 7 storage ADRs (#118/D043, MERGED, squash `6b03d32`) + a research/architecture-reconcile Workflow** (FalkorDB reopened as a candidate graph backend (D044, pending eval); Neo4j Phase B still scoped). **⭐ Top priority now that #117/#118 are merged = the captained benchmark metric run** (write-routing/dedup are LIVE on the product path — the plugin consumes RouterStore via `build_store`, #76; the captained run on real embeddings is the headline-metrics gate). **Remaining SOLO P3 build (now small):** the **captained live `NEO4J_TEST_URI` run** (Phase-A Cypher vs real Neo4j; HARD prereq for **Neo4j Phase B**, D043 PARKED) + the deferred hardening follow-ups (GraphStore cross-process read freshness — a pre-existing residual; markdown MEDs); backend perf-testing; **bge-m3 fallback (PRD-6) — DECISION NEEDED: must-have vs descope for submission**; committed live-benchmark evidence artifacts. See **Active work** + `REMEDIATION_PLAN.md`. Brent's domain.
2. **Captained benchmark runs** — SWE-ContextBench + ContextBench, real embeddings + Brent's key, via the GitHub Actions **Benchmark run** workflow (`.github/workflows/benchmark.yml`; repo secret `ANTHROPIC_API_KEY_BGIBSON1618`, $10 default budget; see `collaborate.html`/`plan.md`). **This is the PRODUCT/capstone success gate** — the PRD criterion (Haiku+harness beats Opus-no-memory on ≥2/5 benchmarks at <~10% overhead) is proven HERE. It is **TEAM-level** (Keith/Ken's harness drives it); Brent's slice *contributes the per-store efficiency/relevancy inputs*, which **require the #3 integration first** (the stores must actually be exercised in a real run — see "built ≠ live"). So: not "optional" for capstone submission, but **gated on #3 + cross-team**, not a solo build.
3. **router↔harness integration — ✅ LARGELY DONE on the live path (#76 / ADR-harness-011, verified in code).** The plugin `_Engine.remember` now calls `Router.write` via `contract.build_store` → `RouterStore` (routed + deduped; `recall` → `route().search`); dreaming routes through the same seam (#79). **Acceptance:** (a) MET for the plugin path (the `MemoryFramework.{write,get,search,all}` stubs remain `NotImplementedError` but are BYPASSED by `build_store` → decide wire-or-retire); (b) integration tests exist (RouterStore #66 adapter evals + the #63 native-pipeline round-trip); (c) the end-to-end efficiency/relevancy numbers on Brent's stores are the **captained benchmark run** — now the real remaining gate (auto-accuracy-profile with the key). **version-highest-wins is NOT a blocker** (resolve independently, #4). **STATUS:** RouterStore (#66/D025) shipped the adapter; the plugin adopted it (#76); remaining = the captained large-benchmark run + the `MemoryFramework` wire-or-retire decision.
   - **Definition of done:** *Brent's slice* is done once write-routing is LIVE + an end-to-end metric run exists on his stores; *capstone/product readiness* additionally needs #2's ≥2/5-benchmark result (team-level). The legacy recall/`memory_remember` surface (REMEDIATION_PLAN) is a **later cleanup, not a wiring blocker**.
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
