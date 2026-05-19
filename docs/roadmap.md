# LineageHub Roadmap

This file tracks the original phased plan, aligned with what exists in the repository today. See the README **Current Status** for a concise summary.

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

Operational run discovery (`runs list`, `runs latest`, and matching API routes) lives in **Phase 3** below.

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

## Phase 3 — Operational Incident Analysis

Goal: Turn LineageHub into a local-first incident triage tool on top of stored lineage + runs.

Delivered in code:

- Run listing and filtering (`runs list`), single-run lookup (`runs show`), and latest-run lookup by job (`runs latest`)
- Incident summaries over failed runs (`incidents summarize`) with downstream impact expansion
- Blast radius ranking (`incidents rank`) with severity bucketing (scoring details in the catalog milestone below)
- Optional API endpoints for operational queries:
  - `GET /runs`, `GET /runs/{run_id}`, `GET /jobs/{job_name}/runs/latest`, `GET /runs/{run_id}/impact`
  - `GET /incidents/summary`, `GET /incidents/rank` (optional query parameters documented in README and [system design](system_design.md): `status`, `since`, `limit`; rank adds `limit_runs`)

Cross-system connectors are planned separately; see [integration_plan.md](integration_plan.md).

---

## Phase 4 — Catalog and Metadata Quality

Goal: Make LineageHub easier to inspect, safer to trust, and better for standalone demos—without external system connectors.

**Delivered in code:**

- Dataset and job catalog CLI (`datasets list` / `show`, `jobs list` / `show`) with optional dataset fields (owner, description, tags, criticality, system)
- Metadata health checks (`validate`, `doctor`) and directed cycle detection (`graph cycles`)
- JSON export workflows (`export lineage`, `export incidents`, including ranked incidents)
- Criticality-weighted blast-radius scoring for `incidents summarize` and `incidents rank`
- Matching read-only API routes, including:
  - `GET /datasets`, `GET /datasets/{name}`, `GET /datasets/{name}/upstream|downstream|impact`
  - `GET /jobs`, `GET /jobs/{job_name}`
  - `GET /validation`, `GET /graph/cycles`, `GET /export/lineage`, `GET /export/incidents`

Example questions:

- What datasets and jobs exist in this environment?
- Who owns this dataset and how critical is it?
- Is the stored lineage graph healthy (orphans, cycles, isolated nodes)?
- Can I export the current metadata for a backup or demo?

---

## Phase 5 — Integration Layer

Goal: Make LineageHub connect with other data platform tools.

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

## Phase 6 — API and Visualization

Goal: Expose lineage metadata through service endpoints and basic visualization.

**Shipped (minimal):** read-only FastAPI app with JSON payloads aligned to the CLI (lineage, runs, incidents, **catalog**, **validation**, **graph cycles**, **export** snapshots), including dataset lineage endpoints and matching **`GET /export/*`** where applicable.

Remaining planned work:

- Authenticated or multi-tenant deployment
- Browser graph visualization
- Richer graph-specific HTTP endpoints beyond CLI parity (optional)

---

## Phase 7 — Natural Language Metadata Queries

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
