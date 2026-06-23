# Backend Durability Audit — sqlite + markdown/OKF stores

> **Date:** 2026-06-23. **Question:** are the durable backends production-durable-under-load, or
> proof-of-concept? **Method:** a multi-agent Workflow (`store-durability-audit`, 52 agents, ~1.8M tokens):
> 8 review lenses (sqlite + markdown/OKF × durability / concurrency / performance / architecture) → each
> finding adversarially verified against source (verifiers *empirically* crash-tested: SIGKILL mid-burst,
> 2–4 concurrent OS processes) → per-store synthesis. Accepted deferrals excluded (brute-force cosine D013,
> the `embed=` seam, WAL-is-SQLite-only). Several reviewer claims were **refuted** by the verifiers (a
> phantom `busy_timeout` regression; a "delete drops both slugs" claim disproven by execution) — what
> remains is filtered, not raw.
>
> **Decision (Brent, 2026-06-23):** do NOT deviate from the Neo4j/graph track now. **Record these findings
> and execute a Backend Durability Hardening Arc immediately after the graph-store/Neo4j thread completes.**
> Tracked in `REMEDIATION_PLAN.md` (queued arc) + `DECISION_LOG.md` D040. See also D039 (Neo4j seam = Bolt).

## Verdicts at a glance

| Store | Verdict | One-line |
|---|---|---|
| `SqliteVectorStore` | **needs-hardening** | Durability core is genuinely production-grade (WAL fail-loud, fsync'd commits, 5s busy_timeout, crash- + multi-process-verified). One real concurrency sharp edge + a hygiene asymmetry + a cheap pre-ANN perf cleanup. |
| `MarkdownStore` / `OKFStore` | **needs-hardening** (effectively **POC persistence**) | Spec-conformant OKF adapter with a genuinely good recall path, but persistence was built for single-process tests: non-atomic writes, no cross-process lock, frozen RAM mirror → **silent data loss + stale recall** under the live MCP+Daydreamer load model. |

**Load model both are judged against:** at runtime an MCP recall/remember path AND a background Daydreamer
both read/write the SAME `$MEMORY_STORE` directory (default `${CLAUDE_PROJECT_DIR}/.cookbook-memory`) —
cross-process concurrency on shared files is real, not hypothetical. Both backends are **live on the product
path**: `_Engine.remember` fans out to all backends via `write_policy=base_all`, so every `remember` writes a
markdown OKF doc and a sqlite row; the Daydreamer routes through the same `build_store`.

---

## `SqliteVectorStore` — needs-hardening

**Headline:** Crash-safety and cross-process concurrency are genuinely solid (WAL enforced fail-loud, per-write
fsync'd commit, 5s busy_timeout), but the store holds one thread-affine sqlite connection — passing it to the
harness's own multi-worker thread pool is a deterministic crash — and `write()` lacks the rollback its
`delete()` sibling has.

### Confirmed gaps

| Sev | Gap | File:line | Fix |
|---|---|---|---|
| **MED** | Single shared **thread-affine** connection (`check_same_thread=True` default) deterministically crashes (`sqlite3.ProgrammingError`) when one store is driven from >1 thread. Reachable via the harness's OWN `run_agent(workers>1)` ThreadPoolExecutor (`agent.py:486-487`, `_store_for_task` returns the same caller store to every worker, `agent.py:631-632`). MED not HIGH because default store is InMemory + workers=1, so it needs an explicit non-default config; failure is loud/immediate, not silent corruption. | `sqlite_store.py:144` | `connect(self.path, check_same_thread=False)` **plus** a `threading.Lock` wrapping every `_conn` access in write/get/search/all/delete (check_same_thread=False alone is unsafe — writes/searches would interleave on one connection). Or a per-thread `threading.local` connection (WAL enforced per connection). |
| **LOW** | `write()` has no `try/except: rollback` that `delete()` already uses — a failure precisely at `commit()` can strand a partial txn on the process-lifetime shared connection that a later unrelated write silently commits. Narrow (embed/json work happens before `execute()`; a BUSY at execute acquires no lock). | `sqlite_store.py:182-191` (vs `delete()` `231-236`) | Wrap write()'s execute+commit in the same `try: ... except: self._conn.rollback(); raise` pattern delete() has. |
| **LOW** | `search()` is O(N) beyond the accepted brute-force cosine: per-query `json.loads` of every row's JSON-TEXT vector **and** a full `MemoryItem` built for ALL N rows before the top-k slice (2 more `json.loads` each). ~1.07–1.17s median recall at N=20k; ~93% of that is the pure-Python cosine scan (the accepted D013 ANN deferral) — these fixes shave the ~7% rider, helping responsiveness modestly, NOT the corpus size at which recall breaks (that's the deferred ANN swap). | `sqlite_store.py:216-217` | (1) Score on `(item_id, vector)` tuples; call `_row_to_item` only for the k survivors. (2) Optionally cache decoded vectors / store a packed float32 BLOB instead of JSON TEXT. |

### Strengths (verified, not assumed)
- **Crash-safety PASSES empirically:** WAL set, each write a single auto-committed fsync'd WAL frame, no naive open/write/truncate. SIGKILL'd mid-burst + reopened cold → all committed rows recovered, 0 torn, `PRAGMA integrity_check` ok. An interrupted write loses at most the single uncommitted item; never corrupts/loses prior committed data.
- **Cross-process concurrent writers serialize correctly under WAL:** 2 and 4 separate OS processes writing concurrently → 0 lock/busy errors, 0 dropped writes.
- **WAL is ENFORCED not assumed** (`sqlite_store.py:151-156`): reads back effective `journal_mode`, raises for any file-backed DB that silently fell back (only in-memory `'memory'` accepted) — defeats a silent downgrade that would reintroduce writer-blocks-reader.
- **busy_timeout = 5000ms** (Python `connect(timeout=5.0)` default, verified live) — writer-vs-writer waits up to 5s instead of instant SQLITE_BUSY. (The claimed `0ms on Python≤3.11` regression does not exist.)
- Cross-process lost-update (INSERT OR REPLACE LWW, no store-layer CAS) is **structurally prevented one layer up**: ADR-dreaming-021 (Accepted) serializes Dream mutation under a basedir flock and explicitly defers store-layer CAS — an accepted documented decision, not an open defect.
- `delete()` already demonstrates the correct rollback-on-failure hygiene (`sqlite_store.py:231-236`).

**Bottom line:** Not poc-only — the durability core is production-grade and empirically verified. But not
production-durable-under-load *as-is*: the thread-affine connection deterministically crashes if the store
is ever handed to a thread pool (the project's own eval harness exposes exactly that path, non-default), the
`write()` rollback asymmetry should be closed, and the O(N) materialization is a cheap pre-ANN cleanup. None
are blockers; none threaten committed data. Targeted hardening.

---

## `MarkdownStore` / `OKFStore` — needs-hardening (effectively POC persistence)

**Headline:** Built as a spec-conformant OKF eval adapter, not a concurrent durable store: every persist is a
non-atomic `write_text` with no lock, fsync, or cross-process read-sync, so under the MCP+Daydreamer
shared-`$MEMORY_STORE` load model it silently **loses** and **staleness-serves** memories. Circle back before relying on it.

### Confirmed gaps

| Sev | Gap | File:line | Fix |
|---|---|---|---|
| **HIGH** | **Non-atomic `write_text`** on the only durable persist path — a crash/concurrent reader mid-write leaves a torn/empty `.md` that the next autoload silently drops, **destroying the PRIOR good copy** on an update. | `okf.py:400` (also `export_bundle` `301,310,317,326`) | `tmp.replace(p)` + `os.fsync` (fd + parent dir) — the EXACT `_write_sidecar_atomic` primitive already in `dreaming/_state.py:240-257` (ADR-013). Same-fs atomic rename: a crash leaves the prior doc intact. Stdlib-only. |
| **HIGH** | **No cross-process lock + frozen RAM mirror** — concurrent same-id writes last-writer-clobber with no detection, AND a long-lived MCP daemon never sees the Daydreamer's writes until restart (stale/split-brain recall). The RAM mirror + inverted index are built ONCE at `__init__`. | `okf.py:392-394,402-409`; `markdown_store.py:58-59` | (1) `fcntl.flock` around the tmp-write+replace in OKFStore.write/delete (the `_state.py:290-322` flock pattern — currently guards only dream state). (2) A read-path refresh seam: reload on bundle-dir mtime change (or explicit `reload()`) so get/search/all + the inverted index reflect peers' committed writes. |
| **HIGH** | `delete()` **rescans + full-parses EVERY `.md`** in the bundle on every call (no break after match) → O(N) reads per delete, O(K·N) per Daydreamer dedup burst, on the same dir recall reads. | `okf.py:411-433` | It already holds the live item (`self._mem.get`, line 420) and write persists at deterministic `_doc_relpath` (`okf.py:277-280,398`): fast-path `(root / _doc_relpath(item)).unlink(missing_ok=True)` + `break`; fall back to the rglob scan only for foreign-imported filenames. |
| **MED** | Corrupt/torn doc on autoload **silently skipped or aborts the whole bundle**: type-less frontmatter dropped with no log/quarantine; an undecodable byte raises `UnicodeDecodeError` out of the unguarded read → **bricks the entire store at construction** (and thus the MCP server + Daydreamer). | `okf.py:344-352` | try/except + `continue` on OSError/UnicodeDecodeError (or `errors='replace'`); warn/quarantine instead of silently dropping a type-less doc. Pairs with the atomic-write fix (removes most torn files at the source). |
| **MED** | Distinct item_ids that **slug to the same filename clobber** on disk (RAM keeps both, disk keeps one) — durable RAM/disk divergence + silent loss on next autoload, even single-process. `'Note A'` and `'note-a'` → both `memory/note-a.md`. | `okf.py:277-280` (`_doc_relpath`/`_slug`) | Append a short hash of the RAW item_id to the slug (`note-a-3f9c1a2b.md`), or refuse/namespace a write whose target path holds a different `x_item_id`. Bites whenever ids are case/punctuation-varying free text (LLM-/Daydreamer-generated). |
| **MED** | Re-writing an item with a changed `okf_type`/`source` **orphans the old doc**; autoload then resurrects the alphabetically-last (not newest) duplicate → silent stale-version resurrection / newer-write loss. | `okf.py:396-400` | Apply delete()'s cleanup on write: before/after persisting, unlink any other on-disk doc whose `x_item_id` equals this id (or unlink the prior canonical path when type/source changed). Trigger today is the dedup-merge path; dedup is default-OFF but permitted → harden before enabling. |
| **MED** | Construction is eager full O(N) disk read + parse + **double index build, whole corpus + postings resident in RAM**, rebuilt every process start with no persisted index. Both cross-process consumers pay it independently + hold duplicate copies. | `okf.py:336-353,388-394`; `markdown_store.py:58-59` | Persist the inverted index (+ optional parsed-item cache) and load incrementally, invalidating by mtime; or lazy-load docs. (The corpus-in-RAM *scan* is partly D013; the eager parse-everything-before-first-answer + per-process duplicate postings are NOT covered.) |

### Strengths (verified)
- The fix primitives **already exist in-repo** — `dreaming/_state.py:240-257` (`_write_sidecar_atomic`, tmp.replace, ADR-013) + the PID+uuid-suffixed sweep marker + the `fcntl.flock` session lock (ADR-014). Hardening is a **port, not an invention**.
- The keyword recall hot path is genuinely fast/well-designed: candidates from an inverted index (prunes zero-overlap docs), in-RAM hydration (no disk read per query), shared BM25 — ranks identically to and out-prunes the shipped `InMemoryStore` reference.
- `delete()` is idempotent and **correct** (unlinks every doc parsing to the id — defends the orphan case write does not); the gap is performance/scale, not correctness.
- The in-process inverted-index thread race (no lock on `_postings`/`_item_tokens`) is real but **low** under the active model (dominant load is cross-PROCESS = separate dicts; no current caller wires one store across worker threads).
- `index.md`/`log.md` drift after write/delete is harmless to recall (non-load-bearing OKF interchange artifacts the retrieval path never reads).
- `MemoryItem.version` round-trips faithfully as provenance/log metadata as documented (never advertised as a CAS token — subsumed by the no-lock gap).
- fsync absence in isolation is low (clean kill/OOM preserves the page cache; only true power-loss in a narrow window loses a returned write) — fold into the atomic-write fix.

**Bottom line:** A clean, spec-conformant OKF adapter with a good recall path, but built as a **proof-of-concept
persistence layer**, not a durable store for the stated cross-process load. Three independent HIGH gaps bite
directly under the live model (non-atomic torn-write loses prior data on update; no lock + frozen mirror →
clobber + stale recall; O(N) delete goes quadratic under dedup bursts on the recall dir). Four MED gaps compound
the same durability/scale story. None are covered by the project's logged deferrals. Fixes are concrete, mostly
stdlib, and the key primitive (tmp+replace, flock) already exists here — a focused circle-back, not a rewrite.

---

## Provenance
Workflow `store-durability-audit` (run `wf_17b9806f-e84`, 2026-06-23). Raw structured result snapshot:
`work/` (gitignored scratch) — re-derivable by re-running the workflow. Load-bearing claims spot-verified
against source by hand (`okf.py:400` non-atomic write; `dreaming/_state.py:240-257` atomic primitive exists;
`sqlite_store.py:182-191` write-vs-delete rollback asymmetry).
