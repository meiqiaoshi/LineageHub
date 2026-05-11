"""Read-only metadata health checks over the SQLite store."""

from __future__ import annotations

import sqlite3
from typing import Any

from lineagehub.graph import find_cycles
from lineagehub.store import (
    MetadataStore,
    _apply_dataset_catalog_migrations,
    _apply_runs_migrations,
)


def validate_metadata(store: MetadataStore) -> dict[str, Any]:
    """Run structural checks on datasets, jobs, runs, and lineage edges.

    Returns a JSON-serializable dict with ``query_type`` ``metadata_validation``.
    ``status`` is ``fail`` if any error is reported, otherwise ``pass`` (warnings allowed).

    Unknown/missing dataset or job references on edges are treated as **errors** (e.g. legacy
    databases loaded with ``PRAGMA foreign_keys`` disabled). Jobs with no lineage edges as
    inputs or outputs, datasets that never appear on an edge, and **directed lineage cycles**
    are **warnings** (cycles use code ``lineage_cycle_detected``).
    """
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    conn = store.connect()
    try:
        _apply_runs_migrations(conn)
        _apply_dataset_catalog_migrations(conn)

        for row in conn.execute(
            """SELECT e.edge_id, e.upstream_dataset_id
               FROM lineage_edges e
               LEFT JOIN datasets u ON u.dataset_id = e.upstream_dataset_id
               WHERE u.dataset_id IS NULL"""
        ).fetchall():
            errors.append(
                {
                    "code": "missing_dataset_reference",
                    "message": (
                        f"Edge {int(row['edge_id'])} references missing upstream "
                        f"dataset_id {int(row['upstream_dataset_id'])}."
                    ),
                    "edge_id": int(row["edge_id"]),
                    "side": "upstream",
                    "dataset_id": int(row["upstream_dataset_id"]),
                }
            )

        for row in conn.execute(
            """SELECT e.edge_id, e.downstream_dataset_id
               FROM lineage_edges e
               LEFT JOIN datasets d ON d.dataset_id = e.downstream_dataset_id
               WHERE d.dataset_id IS NULL"""
        ).fetchall():
            errors.append(
                {
                    "code": "missing_dataset_reference",
                    "message": (
                        f"Edge {int(row['edge_id'])} references missing downstream "
                        f"dataset_id {int(row['downstream_dataset_id'])}."
                    ),
                    "edge_id": int(row["edge_id"]),
                    "side": "downstream",
                    "dataset_id": int(row["downstream_dataset_id"]),
                }
            )

        for row in conn.execute(
            """SELECT e.edge_id, e.job_id
               FROM lineage_edges e
               LEFT JOIN jobs j ON j.job_id = e.job_id
               WHERE e.job_id IS NOT NULL AND j.job_id IS NULL"""
        ).fetchall():
            errors.append(
                {
                    "code": "missing_job_reference",
                    "message": (
                        f"Edge {int(row['edge_id'])} references missing job_id {int(row['job_id'])}."
                    ),
                    "edge_id": int(row["edge_id"]),
                    "job_id": int(row["job_id"]),
                }
            )

        for row in conn.execute(
            """SELECT r.run_id, r.job_id
               FROM runs r
               LEFT JOIN jobs j ON j.job_id = r.job_id
               WHERE j.job_id IS NULL"""
        ).fetchall():
            errors.append(
                {
                    "code": "run_unknown_job",
                    "message": (
                        f"Run {int(row['run_id'])} references missing job_id {int(row['job_id'])}."
                    ),
                    "run_id": int(row["run_id"]),
                    "job_id": int(row["job_id"]),
                }
            )

        for row in conn.execute(
            """SELECT external_run_id, COUNT(*) AS c
               FROM runs
               WHERE external_run_id IS NOT NULL
               GROUP BY external_run_id
               HAVING c > 1"""
        ).fetchall():
            ext = str(row["external_run_id"])
            errors.append(
                {
                    "code": "duplicate_external_run_id",
                    "message": (
                        f"External run id {ext!r} is used by {int(row['c'])} runs; values must be unique."
                    ),
                    "external_run_id": ext,
                    "count": int(row["c"]),
                }
            )

        for row in conn.execute(
            """SELECT j.job_id, j.name,
                      (SELECT COUNT(DISTINCT upstream_dataset_id)
                       FROM lineage_edges WHERE job_id = j.job_id) AS n_in,
                      (SELECT COUNT(DISTINCT downstream_dataset_id)
                       FROM lineage_edges WHERE job_id = j.job_id) AS n_out
               FROM jobs j"""
        ).fetchall():
            n_in = int(row["n_in"])
            n_out = int(row["n_out"])
            if n_in == 0 or n_out == 0:
                warnings.append(
                    {
                        "code": "job_no_lineage_io",
                        "message": (
                            f"Job {row['name']!r} has no lineage edges as inputs "
                            f"({n_in}) or outputs ({n_out})."
                        ),
                        "job": str(row["name"]),
                        "input_dataset_count": n_in,
                        "output_dataset_count": n_out,
                    }
                )

        for row in conn.execute(
            """SELECT d.dataset_id, d.name
               FROM datasets d
               WHERE d.dataset_id NOT IN (
                   SELECT upstream_dataset_id FROM lineage_edges
                   UNION
                   SELECT downstream_dataset_id FROM lineage_edges
               )"""
        ).fetchall():
            warnings.append(
                {
                    "code": "isolated_dataset",
                    "message": f"Dataset {row['name']!r} has no lineage edges.",
                    "dataset": str(row["name"]),
                }
            )

    finally:
        conn.close()

    for cyc in find_cycles(store):
        arrow = " -> ".join(cyc)
        warnings.append(
            {
                "code": "lineage_cycle_detected",
                "message": f"Lineage cycle detected: {arrow}",
                "cycle": list(cyc),
            }
        )

    status = "fail" if errors else "pass"
    return {
        "query_type": "metadata_validation",
        "status": status,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
