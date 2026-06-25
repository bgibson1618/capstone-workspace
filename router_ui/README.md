# Router Memory Inspector

A local web UI to inspect the memories the **cookbook-memory plugin** saves during a benchmark run,
and evaluate how well the **router** routes them. Reads through `memeval`'s public store/router APIs
only — it never parses `.md`/`.db` files. Additive, read-only, zero extra dependencies.

## Run

```bash
./router_ui/run.sh                  # newest agent-memory-harness pipeline substrate (results/v*/_memory)
./router_ui/run.sh --seed --open    # synthetic demo corpus (no real run needed) + open browser
./router_ui/run.sh --store /path/to/_memory
```

Then open the printed `http://127.0.0.1:8765`.
Flags: `--store DIR`, `--port N` (8765), `--profile speed|fusion|accuracy|auto`, `--seed [--force]`,
`--open`, `--margin-threshold F`.

## Views

- **Browse** — every memory, per-backend membership chips that drill into that backend's
  raw retrieval for the memory, metadata, graph edges (rel → target).
- **Routing-effectiveness** — actual on-disk landing vs the router's `classify` + `write_plan`, with
  ⚠ flags for **write-plan-vs-actual asymmetry** and **low classifier margin** (the real mis-route
  signals under the default `base_all` policy, where every memory fans out to all three backends).
- **Query Probe** — a query's routing decision + raw per-backend results (score semantics labeled) +
  the routed engine answer.
- **Capture as eval case** — appends to `router_ui/captured_cases.jsonl`, feeding the fast unit-eval tier.

## How it runs

Imports the installed `memeval` package from the `agent-memory-harness` venv (`make setup` builds it);
`run.sh` sets `PYTHONPATH` to this workspace and `cd`s to the harness so `results/` discovery works.

Built from two architect designs + an implementer (17 tests, real-substrate validated); migrated here
from the harness build and re-verified (tests + live server smoke).
