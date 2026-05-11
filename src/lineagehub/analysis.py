"""Operational incident-style summaries over stored lineage and runs."""

from __future__ import annotations

from typing import Any

from lineagehub.graph import analyze_run_impact
from lineagehub.models import RunImpactRow
from lineagehub.store import MetadataStore

SCORING_METHOD_CRITICALITY_WEIGHTED = "criticality_weighted"

# Weights for ``blast_radius_score`` (sum over affected downstream datasets).
_CRITICALITY_WEIGHTS: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 5,
}
# Missing or unrecognized criticality in the store defaults to the same weight as ``medium``.
UNKNOWN_CRITICALITY_WEIGHT = 2


def criticality_weight(criticality: str | None) -> int:
    """Return the numeric weight for a dataset criticality value.

    ``None`` and unknown strings use ``UNKNOWN_CRITICALITY_WEIGHT`` (2), documented for explainability.
    """
    if criticality is None:
        return UNKNOWN_CRITICALITY_WEIGHT
    key = criticality.strip().lower()
    return _CRITICALITY_WEIGHTS.get(key, UNKNOWN_CRITICALITY_WEIGHT)


def _severity_from_weighted_score(score: int) -> str:
    """Severity buckets from the criticality-weighted blast radius score."""
    if score <= 0:
        return "none"
    if score <= 3:
        return "low"
    if score <= 8:
        return "medium"
    return "high"


def _weighted_blast_and_affected_payload(
    store: MetadataStore, affected: tuple[RunImpactRow, ...]
) -> tuple[int, int, list[dict[str, Any]]]:
    """Returns (weighted_score, affected_count, affected_datasets rows with per-row weights)."""
    rows_out: list[dict[str, Any]] = []
    total_weight = 0
    for row in affected:
        ds = store.get_dataset_by_name(row.name)
        crit = ds.criticality if ds is not None else None
        w = criticality_weight(crit)
        total_weight += w
        rows_out.append(
            {
                "name": row.name,
                "distance": row.distance,
                "source_output": row.source_output,
                "criticality": crit,
                "criticality_weight": w,
            }
        )
    return total_weight, len(affected), rows_out


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
        blast_radius_score, affected_count, affected_payload = _weighted_blast_and_affected_payload(
            store, analysis.affected
        )
        incidents.append(
            {
                "run_id": ext,
                "job_name": r.job_name,
                "status": r.status,
                "output_datasets": list(analysis.output_datasets),
                "affected_datasets": affected_payload,
                "affected_count": affected_count,
                "blast_radius_score": blast_radius_score,
                "severity": _severity_from_weighted_score(blast_radius_score),
                "scoring_method": SCORING_METHOD_CRITICALITY_WEIGHTED,
            }
        )

    max_score = max((i["blast_radius_score"] for i in incidents), default=0)

    return {
        "query_type": "incident_summary",
        "status": status,
        "scoring_method": SCORING_METHOD_CRITICALITY_WEIGHTED,
        "incident_count": len(incidents),
        "incidents": incidents,
        "max_blast_radius_score": max_score,
        "highest_severity": _severity_from_weighted_score(max_score),
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
    Rank incidents by criticality-weighted ``blast_radius_score`` descending
    (stable tie-break: ``run_id`` descending).

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
        "ranking_method": SCORING_METHOD_CRITICALITY_WEIGHTED,
        "scoring_method": SCORING_METHOD_CRITICALITY_WEIGHTED,
        "incidents": [
            {
                "rank": idx,
                "run_id": inc["run_id"],
                "job_name": inc["job_name"],
                "blast_radius_score": inc["blast_radius_score"],
                "severity": inc["severity"],
                "affected_count": inc["affected_count"],
                "scoring_method": inc["scoring_method"],
            }
            for idx, inc in enumerate(ranked_incidents, start=1)
        ],
    }
