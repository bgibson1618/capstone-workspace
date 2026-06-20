# Routing Eval Set (seed) — Cookbook Memory router

**Status:** seed / design draft (Brent + Orchestrator, 2026-06-19). Lives in `capstone-workspace`
during design; transcodes to a runnable JSON/JSONL fixture + a tiny runner in a **Brent-owned repo
path** when we wire it. **Eval-first:** we design the router's rules *against these cases*, then
implement `router.py`, then run.

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
- [ ] grow toward ~50 cases; harvest real retrieval queries from trajectories
- [ ] transcode to a runnable JSONL fixture + a tiny eval runner in a Brent-owned repo path
- [ ] after first real runs: harvest real retrieval queries from trajectories, add them
