"""Operational incident-style summaries over stored lineage and runs."""

from __future__ import annotations

from lineagehub.graph import analyze_run_impact
from lineagehub.store import MetadataStore


def summarize_failed_runs(
    store: MetadataStore,
    status: str = "failed",
    since: str | None = None,
    limit: int | None = None,
) -> dict:
    """
    For each matching run (most recent first), compute downstream impact from that job's outputs.

    Runs without ``external_run_id`` are skipped because ``analyze_run_impact`` keys on external ids.
    """
    rows = store.list_runs(status=status, since=since, limit=limit)
    incidents: list[dict] = []
    for r in rows:
        ext = r.external_run_id
        if ext is None:
            continue
        analysis = analyze_run_impact(store, ext)
        incidents.append(
            {
                "run_id": ext,
                "job_name": r.job_name,
                "status": r.status,
                "output_datasets": list(analysis.output_datasets),
                "affected_datasets": [
                    {
                        "name": row.name,
                        "distance": row.distance,
                        "source_output": row.source_output,
                    }
                    for row in analysis.affected
                ],
            }
        )

    return {
        "query_type": "incident_summary",
        "status": status,
        "incident_count": len(incidents),
        "incidents": incidents,
    }
