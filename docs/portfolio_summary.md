# LineageHub Portfolio Summary

## Project Overview

LineageHub is a local-first operational metadata platform for dataset lineage, pipeline runs, and downstream impact analysis. It stores datasets, jobs, runs, and lineage edges in SQLite and exposes the same capabilities through a CLI, an optional read-only HTTP API, and an optional Streamlit demo UI.

## Problem Solved

Data teams need to answer dependency and failure questions quickly:

- Where does this dataset come from, and what depends on it?
- Which pipeline produced this table, and what is downstream if it fails?
- Is stored metadata healthy (orphan references, cycles, isolated nodes)?
- Can metadata be exported or demonstrated without a full data platform stack?

LineageHub addresses these with a small, standalone tool suitable for portfolio demos and local triage.

## Architecture

```text
JSON lineage / run metadata
        ↓
SQLite metadata store
        ↓
Graph traversal + incident analysis + validation
        ↓
CLI / read-only API / optional Streamlit UI
```

Major layers:

- **Store:** SQLite schemas for datasets, jobs, runs, lineage edges
- **Graph:** upstream, downstream, impact, cycle detection, edge export (text / Mermaid / DOT)
- **Operations:** run listing, incident summarize/rank with criticality-weighted blast radius
- **Quality:** `validate` / `doctor`, export snapshots
- **Interfaces:** argparse CLI, FastAPI JSON API, Streamlit local browser

## Key Features

- Dataset and job catalog (`datasets` / `jobs` list and show)
- Upstream, downstream, and impact queries with `--depth` and `--json`
- Run-aware impact (`impact-run`) and operational run discovery
- Incident summarize and rank over failed runs
- Criticality-weighted blast-radius scoring
- Metadata validation and directed cycle detection
- Lineage and incident JSON export
- Optional Streamlit UI for catalog, graph, incidents, validation, and export preview
- GitHub Actions CI (pytest on Python 3.10 and 3.12)

## Technical Highlights

- Python 3.10+, dataclasses, SQLite
- Breadth-first graph traversal and explainable incident scoring
- Structured JSON payloads shared between CLI and API
- FastAPI read-only service, Streamlit optional extra
- pytest coverage, GitHub Actions workflow

## Demo Workflow

```bash
pip install -e ".[dev,api,ui]"
lineagehub load examples/sample_lineage.json
lineagehub load-runs examples/sample_runs.json
lineagehub validate
lineagehub incidents rank --json
streamlit run scripts/lineagehub_app.py
```

See [demo_walkthrough.md](demo_walkthrough.md) for step-by-step UI checks.

## Resume Bullets

- Built LineageHub, a local-first operational metadata platform using Python and SQLite to track datasets, jobs, pipeline runs, lineage edges, and downstream impact.
- Implemented graph-based upstream/downstream traversal, run-aware incident analysis, criticality-weighted blast-radius scoring, metadata validation, cycle detection, and JSON export workflows.
- Added CLI, read-only FastAPI endpoints, GitHub Actions CI, and a lightweight Streamlit UI for catalog browsing, lineage visualization, and incident review.

## Related Docs

- [README](../README.md)
- [CHANGELOG](../CHANGELOG.md)
- [Roadmap](roadmap.md)
- [Final verification checklist](final_verification.md)
