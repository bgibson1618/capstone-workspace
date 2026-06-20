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
  NOT in the shared repo. Holds: this `CONTEXT.md`, `DECISION_LOG.md` (D001–D015, the AI
  suggested/accepted/changed/rejected log), `ROUTING_EVALS.md`, `TEAM_NOTES.md`, and the agent
  file-memory (`memory/` + `MEMORY.md`). Demo/info material made here may target **Nerdy**
  (tentative — not folded into any plan yet).

## Current state: BUILD COMPLETE
All four owned components are implemented, **stdlib-offline** (real paths behind lazy injection
seams), **eval-first**, independently reviewed, and squash-merged to `main` (PRs **#5–#12**):
- `MarkdownStore` (#5) — OKF-native (delegates to `okf.OKFStore`) + inverted keyword index; keyword-only search (no padding).
- `router.py` (#6) — rule-based scored-signal dispatch to one backend; hardened vs blind adversarials (#7, 58%→83%); Bucket B contested labels adjudicated (#8).
- `SqliteVectorStore` (#9) — `sqlite3` + a deterministic char-n-gram hashing embedder + brute-force cosine; real embeddings (Voyage/bge) + ANN behind `embed=`.
- `GraphStore` (#10) — in-memory link-graph traversal; OKF links (`metadata["okf_links"]`) = edges; seed-then-BFS retrieval. Neo4j behind `uri=`.
- Durable blind routing-eval fixture (#11) + a self-contained-refs cleanup (#12).

`main` is clean and synced; all tests green. An independent `/sanity` (Codex) pass was run and
its findings remediated (durable eval committed, docs reconciled, team items captured below).

## How to verify (run from `~/projects/agent-memory-harness/eval`)
- Smoke gate (the team's CI check): `python3 tests/test_smoke.py` → **67 passed / 0 failed / 1 skipped**.
- Brent's suites: `python3 -m unittest memeval.stores.tests.test_markdown_store memeval.stores.tests.test_sqlite_store memeval.stores.tests.test_graph_store memeval.stores.tests.test_router memeval.stores.tests.test_routing_evals`
- Reproduce the routing number: `python3 -m memeval.stores.tests.test_routing_evals` → **28/31 = 90%** agreement on the blind hard cases.
- Env: `python3` + `uv` (no `python`/`pip` on PATH). The offline path is zero-dependency.

## What's next (the build is DONE — these are optional / future)
1. **Cascade / meta-index (DECISION_LOG D008)** — *designed, NOT built.* Treat the three backends as one OKF concept graph with recursive/cascade fall-through (graph → vector). Brent's domain.
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
