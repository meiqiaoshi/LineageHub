# LineageHub Roadmap

This file tracks the original phased plan. Several Phase 2 and Phase 4 items now exist in code (CLI depth/JSON, graph export, runs loader, `impact-run`, optional FastAPI); see the README **Current Status** for what is implemented today.

## Phase 1 — Local Lineage MVP

Goal: Build a small but complete CLI-based lineage system.

Planned work:

- Create project structure
- Define metadata models
- Create SQLite metadata store
- Load lineage metadata from JSON
- Store datasets, jobs, and lineage edges
- Implement upstream dependency query
- Implement downstream dependency query
- Implement simple impact analysis
- Add basic tests for graph traversal

Success criteria:

- A user can load `examples/sample_lineage.json`
- A user can query upstream datasets for a target dataset
- A user can query downstream datasets for a source dataset
- A user can run impact analysis from the CLI

---

## Phase 2 — Run Metadata and Failure Impact

Goal: Connect lineage relationships with pipeline execution status.

**Delivered in code:** run records with status and `external_run_id` from `load-runs`, `impact-run` (downstream from a run’s job outputs), plus supporting CLI flags and optional API `GET /runs/{run_id}/impact`.

**Not delivered yet:** a “recent failures” or job listing command (roll-up of latest failed runs across jobs).

Original planned work:

- Add run records for jobs
- Store run status and error messages
- Connect failed jobs to output datasets
- Generate downstream impact summaries from failed runs
- Add CLI command for recent failures

Example questions:

- Which datasets were affected by the latest failed job?
- Which downstream assets depend on a failed pipeline output?
- What should be checked after this failure?

---

## Phase 3 — Integration Layer

Goal: Make LineageHub connect with other data platform tools.

Sketch-level alignment with named systems is in [integration_plan.md](integration_plan.md).

Planned work:

- Import run metadata from IngestFlow
- Import quality alerts from SentinelDQ
- Map quality alerts to affected datasets
- Link ingestion failures and quality alerts to lineage graph
- Add integration examples

Example questions:

- Which downstream tables are affected by this SentinelDQ alert?
- Which IngestFlow jobs produced this dataset?
- Which datasets should be checked after this ingestion failure?

---

## Phase 4 — API and Visualization

Goal: Expose lineage metadata through service endpoints and basic visualization.

**Shipped (minimal):** read-only FastAPI app with JSON payloads aligned to the CLI (`GET /datasets/{name}/upstream`, `/downstream`, `/impact`, `/runs/{run_id}/impact`, `/health`, `/datasets`).

Remaining planned work:

- Authenticated or multi-tenant deployment
- Browser graph visualization
- Richer graph-specific HTTP endpoints beyond CLI parity (optional)

---

## Phase 5 — Natural Language Metadata Queries

Goal: Allow users to ask lineage and impact questions in plain English.

Planned work:

- Integrate with a metadata copilot
- Add intent routing for lineage questions
- Translate natural-language questions into lineage API calls
- Produce readable summaries

Example questions:

- What depends on raw_orders?
- If clean_orders fails, what will be affected?
- Where does mart_daily_sales come from?
- Which upstream tables should I check for this dashboard issue?
