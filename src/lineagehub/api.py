"""Read-only FastAPI service for lineage queries (optional dependency group ``api``)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query

from lineagehub.analysis import incident_ranking, summarize_failed_runs
from lineagehub.cli import default_db_path
from lineagehub.graph import (
    analyze_run_impact,
    lineage_downstream_results,
    lineage_impact_results,
    lineage_upstream_results,
)
from lineagehub.output import (
    dataset_catalog_row,
    downstream_payload,
    impact_payload,
    run_impact_payload,
    upstream_payload,
)
from lineagehub.store import MetadataStore, RunRecord

DepthQuery = Literal["direct", "all"]

app = FastAPI(title="LineageHub", version="0.2.0")


def _store() -> MetadataStore:
    return MetadataStore(default_db_path())


def _run_record_public_dict(r: RunRecord) -> dict[str, Any]:
    rid = r.external_run_id if r.external_run_id is not None else str(r.internal_run_id)
    return {
        "run_id": rid,
        "job_name": r.job_name,
        "status": r.status,
        "started_at": r.started_at,
        "ended_at": r.ended_at,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/datasets")
def list_datasets() -> list[dict[str, Any]]:
    store = _store()
    return [
        dataset_catalog_row(
            name=d.name,
            dataset_type=d.dataset_type,
            uri=d.uri,
            owner=d.owner,
            description=d.description,
            tags=d.tags,
            criticality=d.criticality,
            system=d.system,
        )
        for d in store.list_datasets()
    ]


@app.get("/datasets/{name}/upstream")
def dataset_upstream(
    name: str,
    depth: DepthQuery = Query("all", description="direct: one hop; all: transitive closure"),
) -> dict[str, Any]:
    store = _store()
    if store.get_dataset_id_by_name(name) is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {name!r}")
    items = lineage_upstream_results(store, name, depth=depth)
    return upstream_payload(name, depth, items)


@app.get("/datasets/{name}/downstream")
def dataset_downstream(
    name: str,
    depth: DepthQuery = Query("all", description="direct: one hop; all: transitive closure"),
) -> dict[str, Any]:
    store = _store()
    if store.get_dataset_id_by_name(name) is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {name!r}")
    items = lineage_downstream_results(store, name, depth=depth)
    return downstream_payload(name, depth, items)


@app.get("/datasets/{name}/impact")
def dataset_impact(name: str) -> dict[str, Any]:
    store = _store()
    if store.get_dataset_id_by_name(name) is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {name!r}")
    items = lineage_impact_results(store, name, depth="all")
    return impact_payload(name, items)


@app.get("/incidents/summary")
def incidents_summary(
    status: str = Query("failed", description="Run status filter"),
    since: str | None = Query(None, description="Only runs with started_at >= since"),
    limit: int | None = Query(None, ge=1, description="Max runs evaluated"),
) -> dict[str, Any]:
    store = _store()
    return summarize_failed_runs(store, status=status, since=since, limit=limit)


@app.get("/incidents/rank")
def incidents_rank(
    status: str = Query("failed", description="Run status filter"),
    since: str | None = Query(None, description="Only runs with started_at >= since"),
    limit: int | None = Query(None, ge=1, description="Max ranked incidents returned"),
) -> dict[str, Any]:
    store = _store()
    return incident_ranking(
        store,
        status=status,
        since=since,
        limit_runs=None,
        limit_ranked=limit,
    )


@app.get("/runs")
def list_runs(
    status: str | None = Query(None, description="Filter by run status"),
    job: str | None = Query(None, description="Filter by job name"),
    since: str | None = Query(None, description="Only runs with started_at >= since (ISO-8601)"),
    limit: int | None = Query(None, ge=1, description="Max number of rows"),
) -> dict[str, Any]:
    store = _store()
    rows = store.list_runs(status=status, job_name=job, since=since, limit=limit)
    return {
        "query_type": "runs_list",
        "filters": {
            "status": status,
            "job": job,
            "since": since,
            "limit": limit,
        },
        "runs": [_run_record_public_dict(r) for r in rows],
    }


@app.get("/jobs/{job_name}/runs/latest")
def latest_run_for_job(job_name: str) -> dict[str, Any]:
    store = _store()
    latest = store.get_latest_run(job_name)
    return {
        "query_type": "latest_run",
        "job_name": job_name,
        "run": _run_record_public_dict(latest) if latest is not None else None,
    }


@app.get("/runs/{run_id}/impact")
def run_impact(run_id: str) -> dict[str, Any]:
    store = _store()
    try:
        analysis = analyze_run_impact(store, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return run_impact_payload(analysis)
