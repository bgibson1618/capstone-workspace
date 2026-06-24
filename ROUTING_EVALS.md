# Routing Eval Set — Cookbook Memory router

**Status:** active (updated 2026-06-21). The router shipped, was hardened (blind adversarials, 58%→83%),
adjudicated (Bucket B), and the blind set is a **durable committed fixture**:
`eval/memeval/stores/tests/test_routing_evals.py` (reproduce from `eval/`:
`python3 -m memeval.stores.tests.test_routing_evals` → BLIND-hard **28/31 = 90%**). This doc is the design /
provenance record; the **runnable source of truth is that committed fixture.** **Eval-first** throughout.

> **2026-06-21 update — superseding the original sections below.** The eval has since GROWN past the
> original 41-case blind set (D018, PR #28): a **blind multi-lens fan-out** (5 firewalled generators ×
> distinct lenses — surface traps / ambiguity / messy phrasing / boundary / multilingual → synthesizer)
> added a separate measured **`D018_CASES` pool (44 cases — 42 blind-generated + 2 hand-authored
> "D018-harden" regression guards) → fixture now 85 total** (41 `BLIND_CASES`, 31 hard-graded, + 44
> `D018_CASES`; matches the committed fixture's `_EXPECTED_HARD=31` / `_EXPECTED_D018=44` locks), exposing
> the router's **markdown over-routing bias**. Buckets (of the 42 blind-generated): 13 AGREE · 9
> GAP:cheap-fix · 3 GAP:needs-learning (multilingual) · 17 contested(⚠). **Multilingual is out of scope for
> now** — per the English-focus eval decision (`CONTEXT.md`, 2026-06-24), the 3 `GAP:needs-learning`
> multilingual cases are **deferred** (the English coding workload doesn't exercise them); they are
> measured-only, not a current target. The **9 cheap-fix gaps were then fixed** by 7 narrow router rules (D018 cheap-fix,
> PR #29) — speed profile **50%→73%** on the D018 set, golden 5→12, BLIND unchanged at 28/31.
> **Still open:** the 3 multilingual `GAP:needs-learning` and the 17 contested labels (measured, awaiting a
> separate adjudication pass). **Update (D021/D022):** the semantic exemplar classifier (PR3b-2, #49 merged)
> was *measured* — it recovered 2/3 multilingual but regressed English (not eligible standalone), and the
> rules→semantic hybrid was scoped out (the offline embedder can't separate the cases); multilingual routing
> is deferred to the **learned north-star (D007)**, NOT gamed. The TODO list further down is the ORIGINAL plan,
> largely superseded — see DECISION_LOG **D018/D021/D022** for the authoritative state.

## What this measures
Best-first **routing accuracy**: for a query, does `router.route(query)` pick the intended backend?
- **golden** → hard assertions (must route correctly — the "unit test" tier; target 100%).
- **edge / adversarial** → measured accuracy (report it, drive it up; *not* required to hit 100%).

Report three numbers: golden-pass (must stay 100%), edge accuracy, adversarial accuracy.

## Backends & the signal hypotheses they test
| Backend | Role | Provisional signals (the rules we'll design) |
|---|---|---|
| **markdown** | literal recall | exact identifiers, code symbols (`snake_case`/`CamelCase`/paths), quoted strings, short keyword lookups, "name/value of X" |
| **graph** | relationships | relational predicates (depends on / calls / uses / conflicts / related to / connected), ≥2 named entities + a relation |
| **vectors** | semantic | conceptual "why"/rationale, paraphrase, summarize, topical — **and the default** when no literal/relational signal fires |

## Design guards
- **Self-confirming risk** — don't only write cases that match the rules we already imagine; the `adversarial` tier deliberately breaks them.
- **Contested labels (⚠)** — some adversarial cases have no obvious right answer; their `expected` is *provisional*, and resolving each is itself a design decision (maybe by team convention). Don't treat ⚠ as ground truth.
- **Self-authored bias** — these are hand-written. Plan to harvest *real* retrieval queries from agent trajectories once the harness runs, and fold them in.

## Cases

| # | query | expected | tier | why (the signal) |
|---|---|---|---|---|
| 1 | `MemoryStore protocol` | markdown | golden | bare known identifier → literal lookup |
| 2 | `parse_frontmatter signature` | markdown | golden | code symbol (snake_case) → exact code recall |
| 3 | `TODO(brent) in stores` | markdown | golden | literal marker/tag lookup |
| 4 | `DEFAULT_BUDGET_USD` | markdown | golden | exact constant name |
| 5 | `okf.py search method` | markdown | golden | filename + member → literal |
| 6 | `what depends on schema.py` | graph | golden | dependency relation |
| 7 | `what calls Router.route` | graph | golden | caller relation |
| 8 | `how is the dreaming worker connected to the stores` | graph | golden | "connected to" relation between components |
| 9 | `what conflicts with the offline-only guarantee` | graph | golden | conflict / contradiction edge |
| 10 | `modules that use OKFStore` | graph | golden | "use" relation → dependents |
| 11 | `why did we choose keyword-only search` | vectors | golden | conceptual "why" / rationale |
| 12 | `our reasoning on embedding model tradeoffs` | vectors | golden | topical, no exact token |
| 13 | `notes about not peeking at future timestamps` | vectors | golden | paraphrase of `as_of` → semantic |
| 14 | `summary of the OKF integration decision` | vectors | golden | "summary" → semantic synthesis |
| 15 | `what should I work on next` | vectors | edge | no literal/relational signal → semantic **default** |
| 16 | `Voyage embeddings` | markdown | edge | short keyword (literal) — but borders the embedding-decision *rationale* (semantic) |
| 17 | `the schema freeze` | markdown | edge | short noun phrase, literal-ish — but could be the semantic *discussion* |
| 18 | `what's related to the cost tracker` | graph | edge | "related to" is a graph signal, but the query is vague |
| 19 | `why is parse_frontmatter slow` | vectors | adversarial | contains a code token (markdown signal) but it's a semantic "why" — the code-token rule mis-routes |
| 20 | `what's the exact name of the frozen contract file` | markdown | adversarial | question phrasing ("what's the…") but literal intent (a filename) — the question→vectors rule mis-routes |
| 21 | `everything that came up when we froze schema.py` | ⚠ graph | adversarial | implies related items (graph) with no relational keyword + "came up" is semantic — contested (graph vs vectors) |
| 22 | `compare the markdown store to the sqlite store` | ⚠ graph | adversarial | two named entities + relation (graph) but "compare" wants semantic synthesis — contested |
| 23 | `Router` | markdown | adversarial | single identifier → literal by the short-keyword rule, but the agent may want *everything about* Router |

## Hardening round 1 — blind adversarial (2026-06-19)

Four subagents (firewalled from `router.py`) each designed adversarial queries under a
distinct lens: surface-form traps · genuine ambiguity · messy/real phrasing · boundary inputs.
41 blind queries run through router v1:

- **Before fixes: 18/31 = 58%** on hard cases (down from 100% on the self-authored seed — the
  blind set found gaps the seed never could). **0 crashes.**
- **Fixes** (added to `test_router.py` as regression guards): `import` + impact
  (`rename`/`impact`/`affect`/`what breaks`) graph signals; broadened `relate`; dropped the
  `using` false-positive; reclassified `called` (naming) → literal; accepted `name for`;
  guarded zero-token inputs (empty/whitespace/punctuation → semantic default, not markdown).
- **After fixes: 26/31 = 83%.** No seed regressions.

The remaining 5 misses are NOT clean bugs:
- **Known limitations (not v1-rule-fixable):** "how the notes *connect to* the idea" (topical use
  of a structural word — needs semantics); non-English relational verbs ("¿Qué función *llama a*…").
- **Bucket B — contested, awaiting Brent's adjudication:** "everything we know about X"
  (graph vs markdown); "compare X to the one we rejected" (vectors vs graph); "tradeoff between
  X and Y" (the `between…and` rule fires graph; blind says vectors).

## TODO
- [x] round 1 hardening done (blind adversarial, 58% → 83%) — see above
- [x] Bucket B contested labels adjudicated (D012) and tested
- [x] **durable runner committed** → `eval/memeval/stores/tests/test_routing_evals.py` (the 41 blind queries + a reproducible scorer; current router = **90% agreement on hard cases**, the 3 disagreements documented as adjudicated/known-limits). Reproduce: `cd eval && python3 -m memeval.stores.tests.test_routing_evals`
- [x] grow toward ~50 cases — SUPERSEDED: D018 grew the fixture to **85** cases (41 `BLIND_CASES` + 44 `D018_CASES`; blind multi-lens fan-out)
- [ ] harvest real retrieval queries from trajectories; transcode to a JSONL fixture (gated on the harness
      integration — still open; the inline-tuple fixture is the source of truth meanwhile)
- [ ] after first real runs: harvest real retrieval queries from trajectories, add them
