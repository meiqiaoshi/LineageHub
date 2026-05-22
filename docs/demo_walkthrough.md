# Local Demo Walkthrough

This guide runs the optional Streamlit UI against the checked-in sample data. The UI is read-only and reuses the same SQLite store and Python modules as the CLI.

## Prerequisites

- Python 3.10+
- Sample files: `examples/sample_lineage.json`, `examples/sample_runs.json`

## 1. Install the project

From the repository root:

```bash
pip install -e ".[dev]"
```

## 2. Install UI dependencies

```bash
pip install -e ".[ui]"
```

## 3. Load sample lineage

```bash
lineagehub load examples/sample_lineage.json
```

## 4. Load sample runs

```bash
lineagehub load-runs examples/sample_runs.json
```

Use a different database path if needed:

```bash
lineagehub --db /tmp/lineage.db load examples/sample_lineage.json
lineagehub --db /tmp/lineage.db load-runs examples/sample_runs.json
```

Set `LINEAGEHUB_DB` or pick the path in the app sidebar when launching the UI.

## 5. Launch the Streamlit app

```bash
streamlit run scripts/lineagehub_app.py
```

Open the URL shown in the terminal (default `http://localhost:8501`).

## 6. Browse the dataset catalog

Scroll to **Dataset catalog** and confirm datasets such as `raw_orders` and `sales_dashboard` appear with type, owner, and criticality.

## 7. Inspect one dataset

Under **Dataset detail**, choose `sales_dashboard` (or any dataset). Review catalog fields, producer/consumer jobs, and upstream/downstream tables.

## 8. View the lineage graph

In **Lineage graph**, pick a root dataset, set direction (e.g. downstream) and depth (e.g. all). If Graphviz is installed, a diagram renders; otherwise use the DOT source or edge list.

## 9. Check incident ranking

Open **Incident ranking** after sample runs are loaded. Failed runs should appear ranked by criticality-weighted blast radius.

## 10. Run validation

**Metadata validation** should report pass/fail, error and warning counts, and lineage cycle count for the loaded graph.

## Export preview

Use **Export preview** to download lineage or incident JSON consistent with `lineagehub export` CLI output.

## Related docs

- [README](../README.md) — CLI and API overview
- [CHANGELOG](../CHANGELOG.md) — release notes
