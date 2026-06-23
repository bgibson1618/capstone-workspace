# Performance Optimizations for Local Stores (SQLite & Markdown)

This document details recommendations for optimizing the performance of the **`SqliteVectorStore`** and **`MarkdownStore`** in the **agent-memory-harness** project.

---

## 1. Vector Store Optimization: `sqlite-vec` & `usearch`

Currently, `SqliteVectorStore` executes brute-force cosine similarity queries inside the Python interpreter, which scales poorly at $O(N)$ CPU execution.

### Upgrade A: `sqlite-vec` (SQL-Native, SIMD-Accelerated)

`sqlite-vec` is a C extension for SQLite that implements vector similarity queries directly inside SQL.

* **Key Benefits:**
  * **C-Speed Executions:** Vector mathematics are handled natively in C rather than Python.
  * **SIMD Hardware Acceleration:** Automatically utilizes AVX (Intel/AMD) or NEON (ARM/Apple Silicon) instructions to parallelize floating-point calculations.
  * **Memory Efficiency:** Avoids loading the entire vector database into Python memory to compute similarity.
* **SQL Implementation Pattern:**

```sql
-- Create a virtual table for 256-dimension embeddings (default hashing embedder)
CREATE VIRTUAL TABLE items_vector USING vec0(
    item_id TEXT PRIMARY KEY,
    embedding float[256]
);

-- Insert array data as raw bytes (float32 array)
INSERT INTO items_vector(item_id, embedding) VALUES (?, ?);

-- Perform cosine similarity query in a single query
SELECT item_id, distance 
FROM items_vector 
WHERE embedding MATCH ? AND distance_group = 'cosine'
ORDER BY distance 
LIMIT ?;
```

* **Python Integration:**
  Requires the `sqlite-vec` library. Connection setup:
  ```python
  import sqlite3
  import sqlite_vec

  conn = sqlite3.connect("memory.db")
  conn.enable_load_extension(True)
  sqlite_vec.load(conn)
  conn.enable_load_extension(False)
  ```

### Upgrade B: `usearch` (Embedded HNSW Index)

If transitioning to a real model (e.g. Voyage dense embeddings) requiring an Approximate Nearest Neighbor (ANN) index:
* **`usearch`** is a single-header C++ HNSW index library with clean Python bindings.
* It operates entirely in-process (no service daemon needed) and can be serialized as a binary BLOB in SQLite, making it highly portable.

---

## 2. Markdown Store Optimization: SQLite FTS5 (Full-Text Search)

Currently, the `MarkdownStore` reads all markdown files on startup, maintains an in-memory postings dictionary, and executes Okapi BM25 ranking in Python.

### The Upgrade: SQLite FTS5

**FTS5** is a built-in virtual table module in SQLite designed for high-performance full-text search. It handles tokenization, inverted indexing, and Okapi BM25 natively in C.

* **Key Benefits:**
  * **Zero New Dependencies:** It is compiled into SQLite by default and already present in Python's standard `sqlite3` library.
  * **Instant Startup:** Eliminates scanning all files on disk to rebuild the index on startup; the postings list is stored persistently in SQLite.
  * **Native BM25:** Okapi BM25 is computed natively in C.

### Integration with OKF (Open Knowledge Format) Files

To preserve the requirement of human-readable `.md` files on disk (portability), you can use FTS5 as a **write-through query cache**:

```
[Write Path]
MemoryItem ---> Write to disk as /type/id.md (OKF Standard)
            ---> Write text to SQLite FTS5 virtual table

[Search Path]
Query      ---> Query FTS5 Index (BM25 matches computed natively in C)
            ---> Returns top-k matching item_ids
            ---> Load only the top-k files from disk
```

### FTS5 SQL Implementation Pattern:

```sql
-- Initialize the virtual search table
CREATE VIRTUAL TABLE docs_search USING fts5(
    item_id UNINDEXED, -- Store the ID without index parsing
    content
);

-- Insert content to index
INSERT INTO docs_search(item_id, content) VALUES (?, ?);

-- Query using built-in bm25 ranking (more negative score = better match)
SELECT item_id, bm25(docs_search) AS rank_score 
FROM docs_search 
WHERE docs_search MATCH ? 
ORDER BY rank_score 
LIMIT ?;
```
