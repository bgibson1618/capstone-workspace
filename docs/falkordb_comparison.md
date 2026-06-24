# FalkorDB vs. Neo4j Comparison for Agent Memory Harness

> **⚠️ NOT AUTHORITATIVE.** *Research input — graded PARTIAL by D043; FalkorDB REOPENED as a candidate
> pending eval (D044). Not an active plan.* (See `DECISION_LOG.md` D043/D044; stdlib-offline stays the
> test floor, not a feature ceiling.)

This document outlines the architectural comparison between **FalkorDB** and **Neo4j** specifically for the **agent-memory-harness** project, along with a draft implementation of `FalkorGraphStore` satisfying the `MemoryStore` protocol.

---

## 1. Architectural Differences & Tradeoffs

| Feature | FalkorDB | Neo4j |
| :--- | :--- | :--- |
| **Core Engine** | Sparse Matrix (GraphBLAS) | Native Graph (Pointer-chasing) |
| **Environment** | C-based Redis Module | JVM-based |
| **Operational Overhead** | Extremely low, instant startup, low memory footprint | Higher heap/page cache memory overhead, slower startup |
| **Local/CI Testing** | Supported via embedded `falkordblite` | No native embedded library; requires mocks or running docker |
| **Cypher Support** | Substantial subset of openCypher | Comprehensive, mature Cypher implementation |
| **Ecosystem Maturity** | Newer (formerly RedisGraph); growing AI/GraphRAG focus | Highly mature, extensive libraries (APOC, Graph Data Science) |

### Key Tradeoffs for this Harness

* **Unit Testing & CI (The Biggest Advantage):**
  Using Neo4j in local unit tests forces you to use mocks like `FakeBoltDriver` because spinning up a JVM Neo4j instance is heavy and slow. With FalkorDB, you can use **`falkordblite`**, which automatically spins up a clean, embedded Redis server with the FalkorDB module in Python. This allows you to write real integration tests without mocking.
* **Resource Consumption:**
  Since this project runs locally for developers (e.g., under `/home/brent-gibson/projects/agent-memory-harness`), a lightweight Redis module is much easier to run than a full Neo4j server, which requires pre-allocation of JVM heaps.
* **GraphRAG Optimization:**
  FalkorDB is specifically marketed and tuned for GraphRAG and LLM memory application patterns. The GraphBLAS matrix operations provide predictable, low-latency multi-hop traversals.

---

## 2. FalkorGraphStore Implementation Outline

This code matches the design of [neo4j_store.py](file:///home/brent-gibson/projects/agent-memory-harness/eval/memeval/stores/neo4j_store.py) to preserve Phase A parity by pulling as-of-visible nodes from FalkorDB and delegating scoring and BFS to a transient in-memory `GraphStore`.

```python
\"\"\"FalkorDB graph-store backend. Implements ``MemoryStore``.

Serves as a drop-in replacement for Neo4jGraphStore. When use_lite=True, it
manages a local embedded Redis server via falkordblite, making it suitable
for zero-dependency unit testing and local offline runs.
\"\"\"

from __future__ import annotations

import json
from typing import Any, Optional

from ..schema import MemoryItem
from .graph_store import GraphStore, _MAX_DEPTH


_NODE_LABEL = "Memory"
_NODE_MERGE = f"MERGE (n:{_NODE_LABEL} {{item_id: $item_id}}) SET n += $props"
_REL_MERGE = (
    f"MERGE (a:{_NODE_LABEL} {{item_id: $src}}) "
    f"MERGE (b:{_NODE_LABEL} {{item_id: $tgt}}) "
    f"MERGE (a)-[r:REL {{rel_type: $rel}}]->(b)"
)
_SEARCH_MATCH = (
    f"MATCH (n:{_NODE_LABEL}) WHERE $as_of IS NULL OR n.timestamp <= $as_of RETURN n"
)
_GET_MATCH = f"MATCH (n:{_NODE_LABEL} {{item_id: $id}}) RETURN n"
_ALL_MATCH = f"MATCH (n:{_NODE_LABEL}) RETURN n ORDER BY n.seq"
_DELETE = f"MATCH (n:{_NODE_LABEL} {{item_id: $id}}) DETACH DELETE n"


class FalkorGraphStore:
    \"\"\"Typed graph ``MemoryStore`` over FalkorDB or FalkorDBLite.\"\"\"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        graph_name: str = "memory_harness",
        *,
        use_lite: bool = False,
        max_depth: int = _MAX_DEPTH,
        embed: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self.host = host
        self.port = port
        self.graph_name = graph_name
        self.use_lite = use_lite
        self._max_depth = max(0, int(max_depth))
        self._embed = embed
        self._seq = 0
        self._closed = False
        
        # Connect to client/embedded database
        self._client, self._graph = self.connect()
        self._ensure_index()

    def connect(self) -> tuple[Any, Any]:
        \"\"\"Lazily import falkordb (or falkordblite) and establish connection.\"\"\"
        if self.use_lite:
            try:
                import falkordblite  # lazy import
            except ImportError as exc:
                raise RuntimeError(
                    "FalkorGraphStore(use_lite=True) requires 'falkordblite' package. "
                    "Run `pip install falkordblite` to use the embedded engine."
                ) from exc
            client = falkordblite.FalkorDB()
            graph = client.select_graph(self.graph_name)
        else:
            try:
                import falkordb  # lazy import
            except ImportError as exc:
                raise RuntimeError(
                    "FalkorGraphStore requires 'falkordb' package. "
                    "Run `pip install falkordb` or set use_lite=True."
                ) from exc
            client = falkordb.FalkorDB(host=self.host, port=self.port)
            graph = client.select_graph(self.graph_name)
        
        return client, graph

    def _ensure_index(self) -> None:
        \"\"\"Create a range index on item_id for faster MERGE / MATCH query lookups.\"\"\"
        try:
            self._graph.create_node_range_index(_NODE_LABEL, "item_id")
        except Exception:
            # Index might already exist
            pass

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None
        self._graph = None
        self._closed = True

    def __enter__(self) -> "FalkorGraphStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def write(self, item: MemoryItem) -> None:
        if self._closed or self._graph is None:
            raise RuntimeError("write() on a closed FalkorGraphStore")
        
        edges = _parse_edges(item)  # atomic parse-before-mutate (throws on malformed links)
        props = self._props(item)

        self._graph.query(_NODE_MERGE, {"item_id": item.item_id, "props": props})
        for tgt, rel in edges:
            self._graph.query(_REL_MERGE, {"src": item.item_id, "tgt": tgt, "rel": rel})
            
        self._seq += 1

    def _props(self, item: MemoryItem) -> dict:
        return {
            "item_id": item.item_id,
            "content": item.content,
            "timestamp": float(item.timestamp),
            "relevancy": float(item.relevancy),
            "session_id": item.session_id or "",
            "source": item.source or "",
            "tags": json.dumps(list(item.tags)),
            "tokens": int(item.tokens),
            "version": int(item.version),
            "metadata": json.dumps(item.metadata or {}),
            "seq": self._seq,
        }

    def _node_to_item(self, node: Any) -> MemoryItem:
        \"\"\"Parse properties from a FalkorDB Node object back to a MemoryItem.\"\"\"
        props = node.properties
        rel = props.get("relevancy")
        ts = props.get("timestamp")
        ver = props.get("version")
        toks = props.get("tokens")
        
        return MemoryItem(
            item_id=props["item_id"],
            content=props.get("content", ""),
            timestamp=float(ts) if ts is not None else 0.0,
            relevancy=float(rel) if rel is not None else 1.0,
            session_id=props.get("session_id") or None,
            source=props.get("source") or None,
            tags=json.loads(props.get("tags") or "[]"),
            tokens=int(toks) if toks is not None else 0,
            version=int(ver) if ver is not None else 1,
            metadata=json.loads(props.get("metadata") or "{}"),
        )

    def get(self, item_id: str) -> Optional[MemoryItem]:
        if self._closed or self._graph is None:
            raise RuntimeError("operation on a closed FalkorGraphStore")
            
        result = self._graph.query(_GET_MATCH, {"id": item_id})
        for row in result.result_set:
            return self._node_to_item(row[0])  # row[0] is the matched Node object
        return None

    def all(self) -> list[MemoryItem]:
        if self._closed or self._graph is None:
            raise RuntimeError("operation on a closed FalkorGraphStore")
            
        result = self._graph.query(_ALL_MATCH)
        return [self._node_to_item(row[0]) for row in result.result_set]

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        as_of: Optional[float] = None,
        **kwargs: Any,
    ) -> list:
        \"\"\"Retrieves nodes matching timestamp bounds and delegates to transient GraphStore.\"\"\"
        if self._closed or self._graph is None:
            raise RuntimeError("operation on a closed FalkorGraphStore")
            
        result = self._graph.query(_SEARCH_MATCH, {"as_of": as_of})
        items = [self._node_to_item(row[0]) for row in result.result_set]

        transient = GraphStore(max_depth=self._max_depth, embed=self._embed)
        for item in items:
            transient.write(item)
        return transient.search(query, k=k, as_of=as_of, **kwargs)

    def delete(self, item_id: str) -> bool:
        if self._closed or self._graph is None:
            raise RuntimeError("delete() on a closed FalkorGraphStore")
            
        result = self._graph.query(_DELETE, {"id": item_id})
        deleted_count = result.statistics.nodes_deleted
        return deleted_count > 0


def _parse_edges(item: MemoryItem) -> list:
    \"\"\"Extract (target_id, relation) pairs using GraphStore's parser.\"\"\"
    return GraphStore(max_depth=0)._parse_edges(item)
```
