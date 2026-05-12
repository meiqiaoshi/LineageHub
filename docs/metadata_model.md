# LineageHub Metadata Model

## Overview

LineageHub stores metadata about datasets, jobs, runs, and lineage edges.

The model centers on **dataset-level** lineage. A dataset can depend on one or more upstream datasets, and one upstream dataset can affect many downstream datasets.

---

## Entity: Dataset

A dataset is a data asset that can be produced, consumed, monitored, or queried.

Examples:

- raw table
- cleaned table
- analytics mart
- feature table
- dashboard dataset
- exported file

Suggested fields:

| Field | Description |
|---|---|
| dataset_id | Internal unique identifier |
| name | Human-readable dataset name |
| type | Dataset type, such as table, file, mart, dashboard |
| uri | Physical or logical location |
| description | Optional description |
| owner | Optional owning team or role |
| tags | Optional list of string labels (lineage JSON); stored as JSON text in SQLite |
| criticality | Optional business criticality: `low`, `medium`, `high`, or `critical` (loader rejects other values) |
| system | Optional logical system label for the asset (lineage JSON key **`system`**) |
| created_at | Metadata creation timestamp |
| updated_at | Last metadata update timestamp |

Example:

```json
{
  "name": "raw_orders",
  "type": "table",
  "uri": "duckdb://warehouse/raw_orders",
  "owner": "ingestion-team",
  "description": "Bronze-layer raw order events.",
  "tags": ["bronze", "orders"],
  "criticality": "low",
  "system": "duckdb"
}
```

### Implementation note (JSON, Python, SQLite)

Lineage JSON uses the key **`type`** for dataset kind (see table above). In Python code the corresponding dataclass field is named **`dataset_type`** so it does not shadow the builtin `type`. The SQLite table column remains **`type`**, matching this document.

Lineage JSON uses **`system`** on datasets for an optional catalog label. The SQLite column is named **`catalog_system`** so it does not collide with the job table’s **`system`** column when joining in SQL. The Python `Dataset` field is **`system`**; the store maps it to **`catalog_system`**.

---

## Entity: Job

A job is a process that reads one or more input datasets and produces one or more output datasets.

Examples:

- ingestion job
- transformation job
- quality check job
- reporting job
- feature generation job

Suggested fields:

| Field | Description |
|---|---|
| job_id | Internal unique identifier |
| name | Job name |
| system | Source system, such as ingestflow, dbt, airflow, manual |
| description | Optional description |
| created_at | Metadata creation timestamp |
| updated_at | Last metadata update timestamp |

Example:

```json
{
  "name": "clean_orders_job",
  "inputs": ["raw_orders"],
  "outputs": ["clean_orders"]
}
```

---

## Entity: Run

A run is one execution of a job.

Suggested fields:

| Field | Description |
|---|---|
| run_id | Internal unique identifier (SQLite row id) |
| external_run_id | Optional stable id from an external system (JSON field `run_id` in `load-runs`); unique when set |
| job_id | Job associated with the run |
| status | success, failed, running, skipped |
| started_at | Run start time |
| ended_at | Run end time |
| error_message | Optional failure message |

Runs are optional for dataset-only graph queries; they enable **run-aware** downstream impact (`impact-run`) when loaded via `lineagehub load-runs`.

---

## Entity: Lineage Edge

A lineage edge represents a directed dependency between two datasets.

Example:

```text
raw_orders -> clean_orders
```

This means `clean_orders` depends on `raw_orders`.

Suggested fields:

| Field | Description |
|---|---|
| edge_id | Internal unique identifier |
| upstream_dataset_id | Source dataset |
| downstream_dataset_id | Dependent dataset |
| job_id | Job that creates the dependency |
| created_at | Metadata creation timestamp |

---

## SQLite tables (reference)

Schema matches `src/lineagehub/store.py` (`SCHEMA_SQL` plus migrations):

```sql
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT,
    uri TEXT,
    description TEXT,
    owner TEXT,
    tags_json TEXT,
    criticality TEXT,
    catalog_system TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    system TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    error_message TEXT,
    external_run_id TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
-- Partial unique index: idx_runs_external_run_id on external_run_id WHERE NOT NULL

CREATE TABLE IF NOT EXISTS lineage_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    upstream_dataset_id INTEGER NOT NULL,
    downstream_dataset_id INTEGER NOT NULL,
    job_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (upstream_dataset_id) REFERENCES datasets(dataset_id),
    FOREIGN KEY (downstream_dataset_id) REFERENCES datasets(dataset_id),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    UNIQUE (upstream_dataset_id, downstream_dataset_id, job_id)
);
```

The live schema is created by `MetadataStore.init_schema()` in `src/lineagehub/store.py` (`SCHEMA_SQL` plus idempotent migrations). Older databases pick up new columns via `ALTER TABLE` for `runs.external_run_id` and the dataset catalog columns above.

Partial unique index on runs (external ids must be unique when present):

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_external_run_id
ON runs(external_run_id) WHERE external_run_id IS NOT NULL;
```

---

## Graph Interpretation

LineageHub can interpret `lineage_edges` as a directed graph.

- Upstream query: follow edges backward
- Downstream query: follow edges forward
- Impact analysis: follow downstream edges from a failed or stale dataset
- **Cycles:** directed cycles are allowed in storage; `validation.py` reports them as warnings (`lineage_cycle_detected`), and `graph.find_cycles` powers `lineagehub graph cycles` for explicit listing

Example graph:

```text
raw_orders -> clean_orders -> mart_daily_sales -> sales_dashboard
```

If `raw_orders` fails, impact analysis should return:

```text
clean_orders
mart_daily_sales
sales_dashboard
```

---

## Incident blast radius and `criticality` (Phase 4)

When pipeline runs are loaded, failed runs can be summarized with a **criticality-weighted** blast radius: each affected downstream dataset contributes a weight derived from its stored **`criticality`** (`low`→1, `medium`→2, `high`→3, `critical`→5). Missing or unknown values use weight **2** (same as `medium`). The score is the **sum** of those weights; **`affected_count`** is still the number of distinct downstream datasets. Severity labels are simple buckets on that sum. Implementation: `src/lineagehub/analysis.py` (`summarize_failed_runs`, `incident_ranking`).

---

## Related documentation

- [System design](system_design.md) — loaders, store, CLI, and optional API
- [Roadmap](roadmap.md) — future phases
