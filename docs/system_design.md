# LineageHub System Design

## Purpose

LineageHub is designed to track how datasets are connected across a data platform. It stores metadata about datasets, jobs, runs, and lineage edges, then uses that metadata to answer upstream, downstream, and impact-analysis questions.

The first version is intentionally small and local-first. It should be easy to run on a developer machine, easy to test, and easy to extend later.

---

## High-Level Architecture

```text
Lineage Metadata Input
        ↓
Loader
        ↓
SQLite Metadata Store
        ↓
Graph Query Layer
        ↓
CLI / optional read-only HTTP API
```

## Main Components

### 1. Loader

The loader reads lineage definitions from JSON files and writes normalized metadata into the local metadata store.

Responsibilities:

- Read lineage definition files
- Validate required fields
- Insert or update datasets
- Insert or update jobs
- Create lineage edges from job inputs and outputs

### 2. Metadata Store

The metadata store persists all lineage-related information.

The store uses SQLite because it is simple, local, and easy to inspect.

Main stored entities:

- datasets
- jobs
- runs
- lineage_edges

### 3. Graph Query Layer

The graph layer treats dataset dependencies as a directed graph.

Example:

```text
raw_orders -> clean_orders -> mart_daily_sales
```

It supports:

- upstream traversal
- downstream traversal
- impact analysis
- simple graph display

### 4. CLI

The primary interface is an **argparse**-based CLI.

Core commands (non-exhaustive):

```bash
lineagehub load examples/sample_lineage.json
lineagehub load-runs examples/sample_runs.json
lineagehub upstream mart_daily_sales
lineagehub downstream raw_orders
lineagehub impact raw_orders
lineagehub impact-run run_001
lineagehub graph mart_daily_sales
lineagehub runs list --status failed
lineagehub runs latest --job clean_orders_job
lineagehub incidents summarize --json
lineagehub incidents rank --json
```

### 5. Optional API layer

An optional **FastAPI** app (`lineagehub.api`) exposes the same structured JSON as **`--json`** CLI output. Install with `pip install -e ".[api]"` and run with Uvicorn.

Example endpoints:

```text
GET /health
GET /datasets
GET /datasets/{name}/upstream
GET /datasets/{name}/downstream
GET /datasets/{name}/impact
GET /runs
GET /jobs/{job_name}/runs/latest
GET /runs/{run_id}/impact
GET /incidents/summary
GET /incidents/rank
```

---

## Design Principles

### Local First

The default workflow runs without cloud services, containers, or external databases.

### Metadata Driven

Lineage relationships should come from structured metadata, not hardcoded logic.

### Simple Graph Model

The first graph model should focus on dataset-to-dataset dependencies. More complex job-level lineage can be added later.

### Extensible Integrations

The system should be designed so future versions can import metadata from ingestion frameworks, data quality tools, or orchestrators.

---

## Example data flow

```text
sample_lineage.json
      ↓
lineagehub load
      ↓
SQLite tables
      ↓
lineagehub upstream / downstream / impact / graph
      ↓
CLI text or JSON — or HTTP GET via optional API
```

---

## Incident analysis flow (Phase 3)

Phase 3 adds operational queries that start from *recent runs* instead of a known `run_id`.

```text
runs table
    ↓
list failed runs (store.list_runs)
    ↓
for each run: resolve job outputs (lineage_edges where job_id)
    ↓
downstream traversal from outputs (graph.analyze_run_impact)
    ↓
incident summary + blast radius scoring (analysis.py)
    ↓
CLI: incidents summarize / incidents rank
API: GET /incidents/summary / GET /incidents/rank
```

Layering is kept explicit and reusable:

```text
store.py  → runs listing + latest-run lookup
graph.py  → lineage traversal + run-aware impact
analysis.py → incident aggregation + scoring + ranking
cli.py    → presentation (text) + JSON flags
api.py    → read-only HTTP endpoints
```

## Future Extensions

Potential future extensions include:

- Importing pipeline run metadata from IngestFlow
- Connecting data quality alerts from SentinelDQ
- Adding natural-language query support through Orion Data Copilot
- Exporting lineage data in OpenLineage-like event format
- Adding a simple graph visualization UI

---

## Related documentation

- [Metadata model](metadata_model.md) — entities and SQLite tables
- [Roadmap](roadmap.md) — phased goals
- [Integration plan](integration_plan.md) — portfolio alignment (future connectors)
