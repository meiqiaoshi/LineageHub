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
lineagehub graph edges raw_orders
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
lineagehub export lineage --format json
lineagehub export incidents
lineagehub export incidents --ranked
lineagehub export incidents --limit 10
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

**Phase 2** added pipeline runs (`load-runs`), run-aware downstream impact (`impact-run`), CLI **`--depth`** / **`--json`**, **`graph edges`** export, and an optional read-only HTTP API.

**Phase 3** added operational incident triage: **`runs list`**, **`runs show`**, **`runs latest`**, **`incidents summarize`** / **`incidents rank`**, plus matching read-only API routes.

**Phase 4 (metadata quality)** adds dataset/job catalog commands, optional catalog fields on datasets, metadata **`validate`** / **`doctor`**, directed **cycle detection**, JSON **export** of lineage and incidents, and **criticality-weighted** blast-radius scoring for incidents (see **Catalog and metadata quality** below). The authoritative shipped list remains under **Current Status**.

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

The checked-in file **`examples/sample_lineage.json`** defines the graph (datasets include optional catalog fields: owner, description, tags, criticality across **low / medium / high / critical**, and system). Inline copy for reference:

```json
{
  "datasets": [
    {
      "name": "raw_orders",
      "type": "table",
      "uri": "duckdb://warehouse/raw_orders",
      "owner": "ingestion-team",
      "description": "Bronze-layer raw order events ingested from the operational database.",
      "tags": ["bronze", "orders", "source-of-truth"],
      "criticality": "low",
      "system": "duckdb"
    },
    {
      "name": "clean_orders",
      "type": "table",
      "uri": "duckdb://warehouse/clean_orders",
      "owner": "platform",
      "description": "Silver-layer validated and deduplicated orders.",
      "tags": ["silver", "orders"],
      "criticality": "medium",
      "system": "duckdb"
    },
    {
      "name": "mart_daily_sales",
      "type": "table",
      "uri": "duckdb://warehouse/mart_daily_sales",
      "owner": "analytics-engineering",
      "description": "Gold daily sales aggregates for reporting and downstream BI.",
      "tags": ["gold", "finance", "aggregates"],
      "criticality": "high",
      "system": "duckdb"
    },
    {
      "name": "sales_dashboard",
      "type": "dashboard",
      "uri": "dashboard://sales/daily",
      "owner": "analytics",
      "description": "Daily sales dashboard used by business stakeholders.",
      "tags": ["sales", "executive", "bi"],
      "criticality": "critical",
      "system": "bi"
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
│       ├── db_path.py
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
    ├── test_graph_cycles.py
    ├── test_loader.py
    ├── test_cli_json.py
    ├── test_formatters.py
    ├── test_runs_loader.py
    ├── test_impact_run.py
    ├── test_store_runs_list.py
    ├── test_cli_runs_list.py
    ├── test_cli_datasets_list.py
    ├── test_cli_datasets_show.py
    ├── test_cli_jobs_list.py
    ├── test_cli_jobs_show.py
    ├── test_cli_validate.py
    ├── test_cli_graph_cycles.py
    ├── test_validation.py
    ├── test_export_lineage.py
    ├── test_export_incidents.py
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

- **`runs list`** / **`runs show`** / **`runs latest`** for recent and per-job run discovery
- **`incidents summarize`** and **`incidents rank`** (blast radius; later **criticality-weighted** in Phase 4)
- Read-only API: **`GET /runs`**, **`GET /runs/{run_id}`**, **`GET /jobs/{job}/runs/latest`**, **`GET /incidents/summary`**, **`GET /incidents/rank`**

### Phase 4 — Catalog, validation, and exports (shipped) + integration (planned)

**Shipped:** **`datasets`** / **`jobs`** catalog CLI, optional dataset catalog fields, **`validate`** / **`doctor`**, **`graph cycles`**, **`export lineage`** / **`export incidents`**, criticality-weighted incident scoring.

**Planned:** import metadata from ingestion pipelines, connect with data quality alerts, link failures with affected datasets, richer metadata from external systems (see [integration plan](docs/integration_plan.md))

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

Example endpoints (response JSON matches CLI `--json` payloads where noted): `GET /health`, `GET /validation`, `GET /graph/cycles`, `GET /graph/edges/{dataset}?direction=downstream&depth=all`, `GET /export/lineage`, `GET /export/incidents` (optional `ranked=true`, `limit`, `limit_runs` when ranked, `status`, `since`), `GET /datasets` (same **`datasets_list`** envelope as **`datasets list --json`**), `GET /datasets/{name}` (same **`dataset_show`** as **`datasets show --json`**), `GET /datasets/{name}/upstream?depth=all`, `GET /datasets/{name}/downstream?depth=direct`, `GET /datasets/{name}/impact`, `GET /jobs`, `GET /jobs/{job_name}`, `GET /runs`, `GET /runs/{run_id}` (same **`run_show`** as **`runs show --json`**), `GET /jobs/{job_name}/runs/latest`, `GET /runs/{run_id}/impact`, `GET /incidents/summary`, `GET /incidents/rank` (optional `limit`, `limit_runs`).

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
lineagehub runs show run_001
lineagehub runs show run_001 --json
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

Rank incidents by weighted blast radius (see **Criticality-aware incident scoring** below):

```bash
lineagehub incidents rank
lineagehub incidents rank --limit 10 --json
lineagehub incidents rank --limit-runs 50 --limit 10 --json
```

`--limit-runs` caps how many failed runs (most recent first) are scored before sorting; `--limit` caps how many ranked rows are returned.

**Blast radius score** is the **sum of criticality weights** over downstream datasets affected by each failed run (not a simple count). **Severity** is derived from that score (simple buckets for demos). **Affected dataset count** is still reported separately. Weights: `low`→1, `medium`→2, `high`→3, `critical`→5; missing or unknown criticality defaults to **2** (same as `medium`). Severity from score: `0`→`none`, `1–3`→`low`, `4–8`→`medium`, `9+`→`high`. Payloads include `scoring_method: criticality_weighted` and per-row `criticality` / `criticality_weight` under `affected_datasets`.

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
lineagehub graph edges raw_orders
lineagehub graph edges mart_daily_sales --direction upstream --depth direct --format text
lineagehub graph edges raw_orders --format mermaid
lineagehub graph edges raw_orders --format dot
lineagehub graph cycles
lineagehub graph cycles --json
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

## Catalog and metadata quality

After loading **`examples/sample_lineage.json`** (datasets may include **owner**, **description**, **tags**, **criticality**, **system**), these commands support catalog hygiene, graph sanity checks, exports, and weighted incident scoring.

### Dataset and Job Catalog

List and inspect datasets and jobs (text or **`--json`**):

```bash
lineagehub datasets list
lineagehub datasets list --json
lineagehub datasets show sales_dashboard
lineagehub datasets show sales_dashboard --json
lineagehub jobs list
lineagehub jobs list --json
lineagehub jobs show clean_orders_job
lineagehub jobs show clean_orders_job --json
```

### Metadata Validation

Check structural issues (orphan references, duplicate external run ids, jobs without lineage I/O, isolated datasets, **directed cycles**) and emit **`pass`** / **`fail`** plus warnings:

```bash
lineagehub validate
lineagehub validate --json
lineagehub doctor
```

### Cycle Detection

List directed cycles in stored lineage (names closed as `A → … → A`):

```bash
lineagehub graph cycles
lineagehub graph cycles --json
```

### Exporting Metadata

Dump the SQLite store as JSON for backups or demos (lineage shape is close to the loader format; **`lineage_edges`** is explicit). Incidents export reuses **`analysis.py`** payloads (optional **`--status`**, **`--since`**, **`--limit`**: for summary, caps runs evaluated; for **`--ranked`**, **`--limit`** caps ranked rows after sort, and **`--limit-runs`** caps runs fed into scoring—same semantics as **`incidents summarize`** / **`incidents rank`**):

```bash
lineagehub export lineage --format json
lineagehub export incidents
lineagehub export incidents --ranked
lineagehub export incidents --limit 10
lineagehub export incidents --ranked --limit 5
lineagehub export incidents --ranked --limit-runs 100 --limit 10
lineagehub export incidents --since 2026-05-01T00:00:00Z --status failed
```

### Criticality-aware incident scoring

Incident summaries and rankings use **criticality-weighted** blast radius (see **Operational incident analysis** above for weights, severity bands, and JSON fields). Set **`criticality`** on datasets in lineage JSON (or via the store) so downstream impact reflects business importance, not only fan-out.

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

**Implemented:** SQLite-backed metadata, JSON loaders (lineage + runs), **`datasets`** / **`jobs`** catalog CLI, **`validate`** / **`doctor`**, **`export lineage`** / **`export incidents`** JSON snapshots, graph traversal with **`--depth`** / **`--json`**, **`graph edges`** export (text / Mermaid / DOT) and **`graph cycles`**, **`impact-run`**, operational **`runs`** (**`list`** / **`show`** / **`latest`**) / **`incidents`** CLI (including **criticality-weighted** blast-radius scoring) and matching **`analysis.py`** logic, and an optional **read-only FastAPI** service (`src/lineagehub/api.py`) that returns the same structured JSON as the CLI (including catalog routes, **`GET /runs/{run_id}`**, **`GET /validation`**, **`GET /graph/cycles`**, **`GET /graph/edges/{dataset}`**, and **`GET /export/*`**). Command-level workflows are summarized under **Catalog and metadata quality**.

**Out of scope:** authenticated or multi-tenant API deployment, web UI, live lineage capture from orchestrators, external system connectors (see [roadmap](docs/roadmap.md)).

---

## Author

Meiqiao Shi
