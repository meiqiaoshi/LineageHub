# LineageHub

LineageHub is a lightweight metadata platform for tracking dataset lineage, pipeline dependencies, and downstream impact analysis.

The project is designed as a practical data engineering portfolio project focused on metadata management, dataset dependency graphs, and operational visibility across data pipelines.

---

## Overview

Modern data platforms often contain many pipelines, tables, reports, and quality checks. As systems grow, it becomes difficult to answer simple but important questions:

- Where did this dataset come from?
- Which pipeline produced this table?
- What downstream tables or reports will be affected if this source fails?
- Which upstream datasets should be checked when a data quality issue appears?
- How are ingestion jobs, datasets, and data quality signals connected?

LineageHub aims to solve these problems by building a small but extensible lineage and impact analysis system.

At its core, LineageHub stores metadata about:

- datasets
- pipeline jobs
- pipeline runs
- upstream and downstream dependencies
- lineage edges between data assets

This metadata can then be queried through a CLI or API to understand how data flows through a platform.

---

## Project Motivation

This project builds on previous data engineering work, including ingestion pipelines, data quality monitoring, and metadata-driven operational tools.

In many real-world data teams, the problem is not only moving data from one place to another. Teams also need to understand how data assets depend on each other and what impact a failure may have.

For example:

```text
raw_orders
    ↓
clean_orders
    ↓
mart_daily_sales
    ↓
sales_dashboard
```

If `raw_orders` fails or becomes stale, the downstream impact may include `clean_orders`, `mart_daily_sales`, and `sales_dashboard`.

LineageHub is designed to make this kind of relationship visible and queryable.

---

## Goals

The main goals of LineageHub are:

1. Track datasets, jobs, and pipeline runs in a metadata store
2. Represent upstream and downstream dataset dependencies as a graph
3. Support impact analysis when a dataset or pipeline fails
4. Provide a simple CLI and optional read-only HTTP API for querying lineage relationships
5. Build a foundation that can later integrate with ingestion, data quality, and natural-language metadata tools

---

## Example Use Cases

### 1. Find upstream dependencies

```bash
lineagehub upstream mart_daily_sales
```

Example output:

```text
Upstream dependencies for mart_daily_sales:

- clean_orders
- raw_orders
```

### 2. Find downstream impact

```bash
lineagehub impact raw_orders
```

Example output:

```text
Downstream assets affected by raw_orders:

- clean_orders
- mart_daily_sales
- sales_dashboard
```

### 3. Export lineage edges for a dataset (default: downstream, all hops)

Using **`examples/sample_lineage.json`**, downstream from the root dataset lists every hop toward dashboards:

```bash
lineagehub graph raw_orders
```

Example output (text mode sorts edges by upstream then downstream name):

```text
clean_orders -> mart_daily_sales
mart_daily_sales -> sales_dashboard
raw_orders -> clean_orders
```

From **`mart_daily_sales`**, default downstream only reaches **`sales_dashboard`**; use **`--direction upstream`** (or start from **`raw_orders`**) to print the full subgraph as above.

### 4. Load lineage metadata from a file

```bash
lineagehub load examples/sample_lineage.json
```

### 5. Load pipeline runs and inspect run-aware impact

After lineage is loaded, run records can be ingested and queried by external id:

```bash
lineagehub load-runs examples/sample_runs.json
lineagehub impact-run run_001
```

---

## Documentation

- [System design](docs/system_design.md)
- [Metadata model](docs/metadata_model.md)
- [Roadmap](docs/roadmap.md)
- [Integration plan](docs/integration_plan.md) — how LineageHub could align with ingestion, quality, and NL tooling (planned only)

---

## Architecture (overview)

```text
Pipeline Metadata
      ↓
LineageHub Loader
      ↓
Metadata Store
      ↓
Lineage Graph Engine
      ↓
CLI / optional read-only API / future UI
```

The default metadata store is local **SQLite**. The graph engine queries dataset relationships from the store and performs upstream, downstream, and impact analysis.

---

## Core Concepts

### Dataset

A dataset is any data asset that can be produced, consumed, or monitored.

Examples:

- raw database table
- cleaned table
- analytics mart
- dashboard dataset
- machine learning feature table

### Job

A job is a process that reads from one or more datasets and produces one or more datasets.

Examples:

- ingestion job
- transformation job
- dbt model
- data quality check
- report generation task

### Run

A run is one execution of a job.

Stored per run (see also [metadata model](docs/metadata_model.md)):

- status
- start and end time
- optional error message
- optional **`external_run_id`** (from `load-runs` JSON `run_id`)

Input and output datasets are defined on the **job**, not duplicated on each run row; **`impact-run`** uses the job’s output datasets as seeds for downstream traversal.

### Lineage Edge

A lineage edge represents a dependency between two datasets.

Example:

```text
raw_orders -> clean_orders
```

This means `clean_orders` depends on `raw_orders`.

---

## Product scope

**Phase 1** established a local workflow: metadata models, SQLite, JSON lineage loading, upstream/downstream/impact queries, and pytest coverage.

**Phase 2** added pipeline runs (`load-runs`), run-aware downstream impact (`impact-run`), CLI **`--depth`** / **`--json`**, **`graph`** export, and an optional read-only HTTP API.

**Phase 3** added operational incident triage: **`runs list`**, **`runs latest`**, **`incidents summarize`** / **`incidents rank`** (with blast-radius scoring), plus matching read-only API routes. The authoritative list of what exists today is under **Current Status** near the end of this README.

### Still out of scope

- Full web UI
- Real-time lineage capture from orchestrators
- Authentication and multi-tenant deployment
- Distributed execution
- Full OpenLineage compatibility
- Production-grade operations (HA, audit logging, and similar)

These may be added in later phases.

---

## Example lineage definition

The checked-in file **`examples/sample_lineage.json`** defines the graph used above (including **`sales_dashboard`** and the job that produces it). Inline copy for reference:

```json
{
  "datasets": [
    {
      "name": "raw_orders",
      "type": "table",
      "uri": "duckdb://warehouse/raw_orders"
    },
    {
      "name": "clean_orders",
      "type": "table",
      "uri": "duckdb://warehouse/clean_orders"
    },
    {
      "name": "mart_daily_sales",
      "type": "table",
      "uri": "duckdb://warehouse/mart_daily_sales"
    },
    {
      "name": "sales_dashboard",
      "type": "dashboard",
      "uri": "dashboard://sales/daily"
    }
  ],
  "jobs": [
    {
      "name": "clean_orders_job",
      "inputs": ["raw_orders"],
      "outputs": ["clean_orders"]
    },
    {
      "name": "daily_sales_job",
      "inputs": ["clean_orders"],
      "outputs": ["mart_daily_sales"]
    },
    {
      "name": "sales_dashboard_refresh",
      "inputs": ["mart_daily_sales"],
      "outputs": ["sales_dashboard"]
    }
  ]
}
```

---

## Repository layout

```text
LineageHub/
├── README.md
├── pyproject.toml
├── examples/
│   ├── sample_lineage.json
│   └── sample_runs.json
├── docs/
│   ├── system_design.md
│   ├── metadata_model.md
│   ├── roadmap.md
│   └── integration_plan.md
├── src/
│   └── lineagehub/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── store.py
│       ├── loader.py
│       ├── graph.py
│       ├── output.py
│       ├── analysis.py
│       └── api.py
└── tests/
    ├── conftest.py
    ├── test_store.py
    ├── test_graph.py
    ├── test_loader.py
    ├── test_cli_json.py
    ├── test_formatters.py
    ├── test_runs_loader.py
    ├── test_impact_run.py
    ├── test_store_runs_list.py
    ├── test_cli_runs_list.py
    ├── test_analysis_summarize.py
    ├── test_cli_incidents_summarize.py
    ├── test_cli_incidents_rank.py
    └── test_api.py
```

---

## Roadmap

### Phase 1 — Local Lineage MVP

- Create metadata models
- Store datasets, jobs, and lineage edges in SQLite
- Load lineage metadata from JSON
- Implement upstream and downstream graph traversal
- Implement CLI commands for lineage queries

### Phase 2 — Runs, impact, and tooling

- Run metadata with external ids and **run-aware** downstream impact (`impact-run`)
- Dataset-level impact and graph traversal with **`--depth`** / **`--json`**
- Graph export for diagrams (**text / Mermaid / DOT**)
- Optional **read-only FastAPI** (`pip install -e ".[api]"`)

### Phase 3 — Operational incident analysis

- **`runs list`** / **`runs latest`** for recent and per-job run discovery
- **`incidents summarize`** and **`incidents rank`** with blast-radius scoring
- Read-only API: **`GET /runs`**, **`GET /jobs/{job}/runs/latest`**, **`GET /incidents/summary`**, **`GET /incidents/rank`**

### Phase 4 — Integration layer

- Import metadata from existing ingestion pipelines
- Connect with data quality alerts
- Link pipeline failures with affected datasets
- Support richer metadata from external systems (see [integration plan](docs/integration_plan.md))

### Phase 5 — Visualization and assistant UX

- Authenticated or multi-tenant API deployment (today’s API is local read-only)
- Simple graph visualization in the browser
- Deeper wiring to a natural-language metadata assistant (see [integration plan](docs/integration_plan.md))

---

## Local setup and usage

Requirements: **Python 3.10+** (create the virtualenv with that interpreter, e.g. `python3.12 -m venv .venv`, so `pip install -e ".[dev]"` succeeds).

Install in editable mode (includes dev dependencies such as pytest):

```bash
pip install -e ".[dev]"
```

Optional **read-only HTTP API** (FastAPI + Uvicorn), same SQLite resolution as the CLI (`LINEAGEHUB_DB` or `./lineagehub.db`):

```bash
pip install -e ".[api]"
LINEAGEHUB_DB=./lineagehub.db uvicorn lineagehub.api:app --reload
```

Example endpoints (response JSON matches CLI `--json` payloads): `GET /health`, `GET /datasets`, `GET /datasets/{name}/upstream?depth=all`, `GET /datasets/{name}/downstream?depth=direct`, `GET /datasets/{name}/impact`, `GET /runs`, `GET /jobs/{job_name}/runs/latest`, `GET /runs/{run_id}/impact`, `GET /incidents/summary`, `GET /incidents/rank`.

Load the sample lineage file into the default SQLite database (`./lineagehub.db`, unless overridden):

```bash
lineagehub load examples/sample_lineage.json
lineagehub upstream mart_daily_sales
lineagehub downstream raw_orders
lineagehub impact raw_orders
```

Load **pipeline runs** (after jobs exist from lineage JSON). External id is the JSON field `run_id`; it is stored as `external_run_id` in SQLite:

```bash
lineagehub load-runs examples/sample_runs.json
```

**Run-aware impact:** from a recorded run, expand downstream from that job’s **output datasets** (failed runs treat outputs as risky; impact is transitive downstream, with hop distance and originating output in JSON):

```bash
lineagehub impact-run run_001
lineagehub impact-run run_001 --json
```

### Operational incident analysis

Phase 3 adds operational queries so investigations do not need to start from a known `run_id`.

List runs (filter and inspect recent failures):

```bash
lineagehub runs list
lineagehub runs list --status failed --json
lineagehub runs list --job clean_orders_job --limit 5
```

Latest run for a job:

```bash
lineagehub runs latest --job clean_orders_job
lineagehub runs latest --job clean_orders_job --json
```

Summarize failed runs and their downstream impact:

```bash
lineagehub incidents summarize
lineagehub incidents summarize --limit 10 --json
```

Rank incidents by blast radius (downstream affected dataset count):

```bash
lineagehub incidents rank
lineagehub incidents rank --limit 10 --json
```

**Blast radius score** is the number of downstream datasets affected. **Severity** buckets are intentionally simple and explainable:

- `0` → `none`
- `1–2` → `low`
- `3–5` → `medium`
- `6+` → `high`

For **upstream** and **downstream**, control whether to show only **immediate** neighbors or the **full transitive** closure:

- `--depth direct` — one hop (direct dependencies or dependents).
- `--depth all` — default; all datasets reachable through the graph, breadth-first from nearest to farthest.

Example:

```bash
lineagehub upstream mart_daily_sales --depth direct
lineagehub downstream raw_orders --depth all
```

Machine-readable JSON (includes **`distance`** — shortest-path hops from the queried dataset):

```bash
lineagehub upstream mart_daily_sales --json
lineagehub downstream raw_orders --depth direct --json
lineagehub impact raw_orders --json
```

Export edges for visualization (**`--direction`**: `upstream` \| `downstream` \| `both`; **`--format`**: `text` \| `mermaid` \| `dot`; defaults: downstream + all hops + text):

```bash
lineagehub graph raw_orders
lineagehub graph mart_daily_sales --direction upstream --depth direct --format text
lineagehub graph raw_orders --format mermaid
lineagehub graph raw_orders --format dot
```

Use a different database path with `--db` or the `LINEAGEHUB_DB` environment variable:

```bash
lineagehub --db /tmp/lineage.db load examples/sample_lineage.json
LINEAGEHUB_DB=/tmp/lineage.db lineagehub impact raw_orders
```

Run tests from the repository root. API tests require FastAPI (install **`[api]`** alongside **`[dev]`**, or use `pip install -e ".[dev,api]"`):

```bash
pytest
```

**Requires Python 3.10+:** the CLI uses `match` / `case` (PEP 634); older interpreters will fail at import time.

**Phase 3 sanity check** (after loading sample data into the default DB, or use `--db`):

```bash
lineagehub load examples/sample_lineage.json
lineagehub load-runs examples/sample_runs.json
lineagehub runs list --status failed --json
lineagehub incidents rank --json
```

Without installing the package globally, point Python at `src/` and invoke the CLI as a module:

```bash
PYTHONPATH=src python -m lineagehub --help
PYTHONPATH=src python -m lineagehub load examples/sample_lineage.json
```

---

## Technology Stack

- Python 3.10+
- SQLite
- **argparse** CLI (`lineagehub` entry point)
- **Dataclasses** for metadata models
- **pytest** for tests (install with **`[dev]`**)
- Optional **FastAPI** + **Uvicorn** read-only API (install with **`[api]`**)

---

## Why This Project Matters

LineageHub demonstrates an important part of modern data engineering beyond basic ETL.

Instead of only building pipelines, this project focuses on understanding and operating a data platform:

- how datasets are connected
- how failures propagate
- how pipeline metadata can be queried
- how data systems become observable and maintainable

This makes the project relevant to roles such as:

- Data Engineer
- Data Platform Engineer
- Analytics Engineer
- Data Infrastructure Engineer

---

## Current Status

**Implemented:** SQLite-backed metadata, JSON loaders (lineage + runs), graph traversal with **`--depth`** / **`--json`**, **`graph`** export (text / Mermaid / DOT), **`impact-run`**, operational **`runs`** / **`incidents`** CLI and matching **`analysis.py`** logic, and an optional **read-only FastAPI** service (`src/lineagehub/api.py`) that returns the same structured JSON as the CLI.

**Out of scope:** authenticated or multi-tenant API deployment, web UI, live lineage capture from orchestrators, external system connectors (see [roadmap](docs/roadmap.md)).

---

## Author

Meiqiao Shi
