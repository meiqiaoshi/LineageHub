"""Operational incident-style summaries over stored lineage and runs."""

from __future__ import annotations

from typing import Any

from lineagehub.graph import analyze_run_impact
from lineagehub.store import MetadataStore


def _severity_from_blast_radius(score: int) -> str:
    """Explainable severity buckets for portfolio demos (score = affected downstream dataset count)."""
    if score <= 0:
        return "none"
    if score <= 2:
        return "low"
    if score <= 5:
        return "medium"
    return "high"


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
        affected_payload = [
            {
                "name": row.name,
                "distance": row.distance,
                "source_output": row.source_output,
            }
            for row in analysis.affected
        ]
        blast_radius_score = len(analysis.affected)
        incidents.append(
            {
                "run_id": ext,
                "job_name": r.job_name,
                "status": r.status,
                "output_datasets": list(analysis.output_datasets),
                "affected_datasets": affected_payload,
                "blast_radius_score": blast_radius_score,
                "severity": _severity_from_blast_radius(blast_radius_score),
            }
        )

    max_score = max((i["blast_radius_score"] for i in incidents), default=0)

    return {
        "query_type": "incident_summary",
        "status": status,
        "incident_count": len(incidents),
        "incidents": incidents,
        "max_blast_radius_score": max_score,
        "highest_severity": _severity_from_blast_radius(max_score),
    }


def incident_ranking(
    store: MetadataStore,
    *,
    status: str = "failed",
    since: str | None = None,
    limit_runs: int | None = None,
    limit_ranked: int | None = None,
) -> dict[str, Any]:
    """
    Rank incidents by ``blast_radius_score`` descending (stable tie-break: ``run_id`` descending).

    ``limit_runs`` caps rows fed into summary (same as ``summarize_failed_runs(..., limit=...)``).
    ``limit_ranked`` caps how many ranked rows appear after sorting (CLI/API ``--limit`` on rank).
    """
    summary = summarize_failed_runs(store, status=status, since=since, limit=limit_runs)
    ranked_incidents = sorted(
        summary["incidents"],
        key=lambda i: (i["blast_radius_score"], i["run_id"]),
        reverse=True,
    )
    if limit_ranked is not None:
        ranked_incidents = ranked_incidents[: int(limit_ranked)]

    return {
        "query_type": "incident_ranking",
        "ranking_method": "affected_dataset_count",
        "incidents": [
            {
                "rank": idx,
                "run_id": inc["run_id"],
                "job_name": inc["job_name"],
                "blast_radius_score": inc["blast_radius_score"],
                "severity": inc["severity"],
                "affected_count": inc["blast_radius_score"],
            }
            for idx, inc in enumerate(ranked_incidents, start=1)
        ],
    }
