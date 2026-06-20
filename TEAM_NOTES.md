# Notes for the team — from Brent (2026-06-19)

Two coordination items surfaced by an independent `/sanity` review of the implemented
stores + router. Both are bigger than my slice, so I'm flagging rather than acting
unilaterally.

## 1. Version invariant: `architecture.md` says highest-version-wins, but no store enforces it

`architecture.md` (~line 49) says a store keeps the highest `MemoryItem.version` as the
current value on a conflicting write. In practice **none of the stores enforce this** — they
all do last-write-wins on `item_id`:

- `harness.InMemoryStore` (the reference), `okf.OKFStore`, and my `MarkdownStore` /
  `SqliteVectorStore` / `GraphStore`.

So either:
- **(a)** highest-version-wins is the **dreaming / persistence layer's** responsibility
  (Scott's conflict-resolution), and `architecture.md` is loosely worded → clarify the doc; or
- **(b)** the stores should enforce it → add a guard in each `write()` (skip/keep the higher
  `version` when an item already exists).

My lean is **(a)** — version conflict-resolution feels like a dreaming-worker concern, not a
per-store one — but it's a contract question for the group. Whichever we pick, let's make
`architecture.md` and the code agree and add a test. (Right now the reference store itself
violates the doc, so this isn't a one-person fix.)

## 2. `project-plan.md` overstates what shipped (production ANN / Neo4j)

`project-plan.md` (~line 181) reads as if the production pieces — SQLite + a real embedding
model + HNSW/FAISS, and a Neo4j typed-traversal graph — were delivered for my slice. What
actually shipped is honest **stdlib v1**: char-n-gram hashing + brute-force cosine, and an
in-memory untyped link graph, with the real/paid path deferred behind injection seams
(`embed=`, `uri=`). This is intentional and documented on my side (DECISION_LOG D013/D014),
but the plan doc should say *"v1 stdlib offline shipped; production embeddings / Neo4j deferred
to the paid path"* so our status is accurate — especially for how we describe the project
externally.
