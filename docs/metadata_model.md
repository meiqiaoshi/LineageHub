# LineageHub Metadata Model

## Overview

LineageHub stores metadata about datasets, jobs, runs, and lineage edges.

The MVP focuses on dataset-level lineage. A dataset can depend on one or more upstream datasets, and one upstream dataset can affect many downstream datasets.

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
| created_at | Metadata creation timestamp |
| updated_at | Last metadata update timestamp |

Example:

```json
{
  "name": "raw_orders",
  "type": "table",
  "uri": "duckdb://warehouse/raw_orders"
}
```

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
| run_id | Internal unique identifier |
| job_id | Job associated with the run |
| status | success, failed, running, skipped |
| started_at | Run start time |
| ended_at | Run end time |
| error_message | Optional failure message |

Runs are not required for the earliest graph-only MVP, but they become important for impact analysis.

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

## MVP SQLite Tables

A possible first schema:

```sql
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT,
    uri TEXT,
    description TEXT,
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
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

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

---

## Graph Interpretation

LineageHub can interpret `lineage_edges` as a directed graph.

- Upstream query: follow edges backward
- Downstream query: follow edges forward
- Impact analysis: follow downstream edges from a failed or stale dataset

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
