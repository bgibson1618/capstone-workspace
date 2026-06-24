> **⚠️ LENS CORRECTION (Brent, 2026-06-23) — read first.** This review was briefed with stdlib-only /
> in-process as "hard constraints." That was an over-statement: **stdlib-offline is the project's TEST FLOOR,
> not a feature ceiling.** The empirical findings below remain valid and useful as a **design risk-map**; the
> "VERDICT: FAIL / reject / confirms-D043" framing is **superseded** — under the corrected lens these are
> **candidate upgrades pending eval-first measurement**, and D043 (FalkorDB) and D039 (Bolt) are reopened.
> See `DECISION_LOG.md` **D044**.

# Cross-Vendor Accuracy Review — `router_architecture_recommendations.md`

> **What this is:** the adjudicated output of a 4-vendor accuracy check (2026-06-23) of the
> research-agent doc `router_architecture_recommendations.md`. Inputs: 3 independent researchers on
> **claude + codex + antigravity** backends (observable `agent-roster` runs, blind to the project's
> prior FalkorDB research), consolidated by a **Codex adjudicating verifier**. `VERDICT: FAIL` below
> was the review's grade **under the briefed (over-stated) lens — superseded by the LENS CORRECTION above.**
> The findings remain valid as a **design risk-map**. Decision recorded in `DECISION_LOG.md` **D044**;
> the reviewed doc is retained, stamped **CANDIDATE-UPGRADE ROADMAP (pending eval).**

---

VERDICT: FAIL
DIMENSIONS:
  - Recommendation accuracy: FAIL
  - Constraint fit: FAIL
  - Decision-log consistency: FAIL
  - Reusable research value: PASS
BLOCKING:
  - docs/router_architecture_recommendations.md: recommends FalkorDB/falkordblite as graph replacement and FakeBoltDriver replacement, conflicting with constraints and D041/D043.
  - docs/router_architecture_recommendations.md: presents non-stdlib MiniLM/usearch/sqlite-vec/FalkorDB components as architecture path rather than optional seams.
  - docs/router_architecture_recommendations.md: FTS5 and vector SQL snippets omit parity/concurrency requirements.
RIGOR: tuned

## Findings

### Consensus Map And Adjudication

| Scope | claude | codex | antigravity | Agree? | Adjudicated verdict |
|---|---:|---:|---:|---|---|
| Rec 1: MiniLM + Voyage hybrid | MISLEADING | MISLEADING | Mixed: TRUE principle, MiniLM setup FALSE, Voyage TRUE | Partial divergence | MISLEADING |
| Rec 2: FalkorDB/falkordblite | FALSE/MISLEADING | FALSE | FALSE/MISLEADING | Yes | FALSE |
| Rec 3: usearch + SQLite BLOB | MISLEADING | MISLEADING | Mixed: usearch true, BLOB concurrency false, SQL false | Yes on risk | MISLEADING |
| Rec 4: Markdown FTS5 cache | MOSTLY-TRUE with caveats | MOSTLY-TRUE with caveats | Partly false, recommends reject as written | Divergence | MOSTLY-TRUE as research input, not as written |
| Latency/cost claims | MISLEADING | UNVERIFIABLE/MISLEADING; cost concept mostly true | MOSTLY-TRUE with caveats | Divergence | MISLEADING |
| Mermaid | MISLEADING | MISLEADING | MISLEADING | Yes | MISLEADING |
| SQL snippets | MISLEADING/FALSE | FALSE/MISLEADING | MISLEADING/FALSE | Yes | FALSE for ANN ordering |

### Per-Recommendation Verdict

**Recommendation 1: Hybrid MiniLM + Voyage AI — MISLEADING.**  
The principle “do not use a generative LLM for routing” is already implemented: `router.py` defaults to a stdlib rule classifier (`eval/memeval/router.py:1-25`, `203-227`, `933-940`). The semantic exemplar classifier exists, but it is explicitly caller-injected and non-default (`router.py:233-240`, `325-390`). MiniLM is not stdlib: the model card requires `sentence-transformers` or `transformers`/`torch` and maps to 384-dimensional vectors, not the doc’s Voyage 1024-dimensional vector path ([Hugging Face MiniLM](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)). Voyage is already correctly behind the vector embed seam (`sqlite_store.py:7-20`, `138-145`, `177-186`). The doc overstates “only vector operations call cloud APIs” because semantic routing could embed every query, and default write policy is `base_all`, which writes to vectors on every write (`router.py:462-469`, `1021-1027`).

**Recommendation 2: FalkorDB/falkordblite — FALSE.**  
PyPI lists `falkordblite` 0.10.0 as requiring Python `>=3.12.0`, while this project requires Python `>=3.11` and declares no required runtime deps (`eval/pyproject.toml:6-9`, `25`, `46-47`; [PyPI falkordblite](https://pypi.org/project/falkordblite/) lines show `Requires: Python >=3.12.0`). PyPI also describes a built-in Redis server that is automatically managed, and redislite examples explicitly start new Redis servers; build notes compile Redis and download/copy the FalkorDB module. That is a managed server subprocess, not an in-process stdlib store. `Neo4jGraphStore` uses the Neo4j Bolt driver (`neo4j.GraphDatabase.driver`) and lazy-imports `neo4j` (`neo4j_store.py:1-4`, `40-44`, `141-156`); `falkordblite` exposes a Redis/FalkorDB Python API, so it cannot be driven by the Neo4j Bolt driver. Replacing `FakeBoltDriver` would also remove tests that intentionally assert Neo4j wire shape and endpoint-creation behavior (`test_neo4j_parity.py:13-19`, `94-110`, `609-651`, `691-723`).

**Recommendation 3: usearch + SQLite BLOB — MISLEADING.**  
The premise is true: `SqliteVectorStore.search()` selects all rows, computes Python cosine in a loop, and sorts by similarity first (`sqlite_store.py:222-245`). USearch is a real in-process ANN library with Python bindings and serialization APIs ([USearch Python docs](https://unum-cloud.github.io/USearch/python/)). But it is a non-stdlib compiled dependency, so it cannot be the default path. The BLOB pattern is the bigger problem: a monolithic in-memory HNSW index serialized back into one SQLite cell needs a cross-process revision/lock/reload design, or concurrent writers can overwrite each other’s index updates even if the `items` rows survive. Treat usearch/sqlite-vec only as optional acceleration behind the existing seam, not as the durable default.

**Recommendation 4: Markdown FTS5 cache — MOSTLY-TRUE as research input, not safe as written.**  
The current MarkdownStore does keep a Python postings index and score with the shared BM25 implementation (`markdown_store.py:51-63`, `123-165`; `harness.py:95-162`). FTS5 is in-process SQLite; this local Python reports SQLite `3.46.1` with `ENABLE_FTS5=1`. But FTS5 is a compile-time SQLite feature, not guaranteed merely by Python stdlib ([SQLite FTS5 docs](https://www.sqlite.org/fts5.html)). Directly replacing the shared scorer with `bm25()` breaks parity: the harness returns `(bm25_score, idf_coverage)` with non-negative IDF and sorts by BM25, then `idf_coverage`, then relevancy/timestamp/id (`harness.py:104-121`, `218-224`; `markdown_store.py:155-159`). SQLite FTS5 `bm25()` returns lower-is-better values and multiplies by `-1` for ordering convenience; it does not expose this project’s secondary `idf_coverage` tie-break ([SQLite bm25 docs](https://www.sqlite.org/fts5.html)). FTS5 is worth a design spike, but as a feature-detected candidate index or as an FTS5-as-SSOT redesign, not as an unqualified write-through cache that skips startup reconciliation.

### Snippets And Claims

The SQL snippet is wrong for ANN second-stage ordering. After ANN returns candidate IDs, the SQL must carry ANN distance/rank/similarity and order by that first. `ORDER BY relevancy DESC` discards vector similarity entirely; the current store sorts by `(-similarity, -relevancy, -timestamp, item_id)` (`sqlite_store.py:241-244`). `IN ($candidate_ids)` is also not a valid single SQLite list binding, and `timestamp <= $as_of` needs a null guard.

The Mermaid diagram is not architecture-of-record. It shows MiniLM, FalkorDB/Lite, usearch BLOB, FTS5, and Voyage as the pipeline, while the actual default is stdlib rule router plus stdlib stores with optional seams.

The latency/cost claims are not established. `<50ms CPU overhead` is plausible for current rule routing and small local stores, but not proven for MiniLM, FalkorDB, or network embeddings. The API-cost principle is directionally right only when semantic routing is local and vector embedding remains behind the vector seam.

## Conflicts With Recorded Decisions

This doc conflicts directly with D041 and D043.

D041 records Neo4j Phase A as a parity floor over Bolt, with `FakeBoltDriver` retained specifically to model Neo4j endpoint creation and guard the forward-reference placeholder bug (`DECISION_LOG.md:459-468`). The doc’s “replace Neo4j/FakeBoltDriver with FalkorDBLite” cuts against that settled decision.

D043 already adjudicated the FalkorDB and local-store performance research as PARTIAL, not adopted. It says falkordblite is a managed subprocess, Python 3.12+/not stdlib, useful only as a CI harness, and that FTS5-as-cache does not fix durability; only FTS5-as-SSOT would (`DECISION_LOG.md:480-489`). This cross-vendor review confirms D043 rather than challenging it.

## Verification Evidence

I independently verified the load-bearing facts from code, recorded decisions, and primary package/docs sources:

- `falkordblite` requires Python `>=3.12.0`; project requires `>=3.11`.
- `falkordblite` manages a Redis/FalkorDB server, not an in-process Python engine.
- `Neo4jGraphStore` uses the `neo4j` Bolt driver and cannot talk to a `falkordblite` Redis/FalkorDB API.
- `sqlite_store.py` is currently a brute-force Python cosine scan.
- Direct FTS5 `bm25()` would break the project’s shared BM25 plus `idf_coverage` ranking parity.
- `ORDER BY relevancy DESC` is wrong for ANN second-stage ranking.

Local package check found `falkordblite`, `falkordb`, `neo4j`, `usearch`, and `sqlite_vec` are not installed, so I did not import-test their runtime behavior locally. The package facts above come from PyPI/vendor docs.

## Residual Risk

MiniLM and FalkorDB latency claims were not benchmarked on Brent’s machine, so their numeric latency verdict is “unproven,” not “disproven.” USearch BLOB serialization support was verified from docs at the path level, but not import-tested locally. These uncertainties do not affect the gate: the doc still violates default-path dependency, process, protocol, and concurrency constraints as written.

## How To Handle The Doc

Keep it only as annotated research input, not authoritative architecture.

Adopt or carry forward only these parts:

- Keep the principle that routing should not depend on a generative LLM.
- Keep Voyage and real embedders behind optional seams.
- Consider FTS5 as a feature-detected performance spike, but preserve scorer parity or explicitly decide to change it; do not present FTS5-as-cache as a durability fix.
- Consider usearch/sqlite-vec only as optional accelerators with a real cross-process index-coherence design.

Do not adopt:

- FalkorDB as a backend replacement.
- falkordblite as a replacement for `FakeBoltDriver`.
- usearch serialized into one SQLite BLOB as the proposed durable/concurrent design.
- The ANN SQL ordering as written.

## Gate Verdict

FAIL. The doc is partially useful as a technology survey, but it is misleading as a project recommendation because it conflicts with the project’s hard constraints and with D041/D043. The single most important takeaway for Brent: **the FalkorDB/falkordblite recommendation should not be followed; it would undo a settled Neo4j parity decision and move non-stdlib subprocess infrastructure into a path that must remain stdlib-only, in-process, and offline.**

## Questions

None.