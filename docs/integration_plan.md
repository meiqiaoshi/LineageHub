# Integration Plan (Portfolio Alignment)

This document describes how LineageHub could connect with other portfolio-style components. **Connectors and multi-system sync described below are not implemented.** LineageHub already ships a **read-only HTTP API** (`lineagehub.api`) that a future assistant or dashboard could call; this file focuses on *cross-repo* integration patterns.

## Role of LineageHub

LineageHub holds **dataset–job–run** metadata and answers graph questions (upstream, downstream, impact). Integrations should treat it as a **metadata sink and query surface**, not as the primary execution engine for ingestion or quality checks.

## Hypothetical upstream systems

### IngestFlow (ingestion orchestration)

**Direction:** IngestFlow → LineageHub.

- Emit **job definitions** (inputs / outputs) when pipelines are registered or deployed, mapped to LineageHub’s lineage JSON shape or store API.
- Emit **run records** on completion (success/failure, timestamps, optional error text), aligned with `load-runs` / `external_run_id` semantics.
- Enables questions such as: which datasets were produced by run `run_xyz`, and what is downstream if that run failed?

### SentinelDQ (data quality monitoring)

**Direction:** SentinelDQ → LineageHub (alerts) and LineageHub → SentinelDQ (context).

- On alert creation, send **dataset identifier**, **severity**, and **rule id** to a future ingestion endpoint or batch job that attaches alerts to existing datasets in the store.
- For investigations, use LineageHub **upstream** / **impact** APIs to list datasets to re-check or to notify owners downstream of the failing asset.

### Orion (natural-language metadata assistant)

**Direction:** Orion ↔ LineageHub HTTP API.

- Orion translates user questions into calls to read-only endpoints:
  - catalog: `/datasets`, `/datasets/{name}`, `/jobs`, `/jobs/{job_name}`
  - metadata quality: `/validation`, `/graph/cycles`, `/graph/edges/{dataset}`, `/export/lineage`, `/export/incidents`
  - lineage queries: `/datasets/.../upstream`, `/downstream`, `/impact`
  - run queries: `/runs`, `/jobs/{job_name}/runs/latest`, `/runs/{run_id}/impact`
  - incident triage: `/incidents/summary`, `/incidents/rank`
- Responses stay structured JSON so Orion can summarize without re-implementing graph logic.

## Contract assumptions

- **Identifiers:** Dataset names and external run ids must be stable and agreed across systems (shared catalog or naming convention).
- **Freshness:** Batch sync (files or periodic jobs) is enough for a portfolio demo; production might need idempotent upserts and versioning (not in scope today).
- **Security:** Today’s API is unauthenticated; any multi-tenant deployment would need authn/authz and tenant-scoped databases—explicitly out of scope until a later phase.

## Related docs

- High-level phases: [roadmap.md](roadmap.md)
- Entity definitions: [metadata_model.md](metadata_model.md)
