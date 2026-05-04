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
GET /runs/{run_id}/impact
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

## Future Extensions

Potential future extensions include:

- Importing pipeline run metadata from IngestFlow
- Connecting data quality alerts from SentinelDQ
- Adding natural-language query support through Orion Data Copilot
- Exporting lineage data in OpenLineage-like event format
- Adding a simple graph visualization UI
