"""Read-only FastAPI service for lineage queries (optional dependency group ``api``)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Query

from lineagehub.db_path import default_db_path
from lineagehub.output import (
    dataset_show_for_name,
    datasets_list_payload,
    downstream_for_dataset,
    export_incidents_payload,
    graph_cycles_for_store,
    graph_edges_json,
    impact_for_dataset,
    incidents_rank_for_store,
    incidents_summary_for_store,
    jobs_list_payload,
    job_show_for_name,
    lineage_export_payload,
    latest_run_payload,
    run_impact_for_run_id,
    run_show_for_run_id,
    runs_list_payload,
    upstream_for_dataset,
)
from lineagehub.store import MetadataStore
from lineagehub.validation import validate_metadata

DepthQuery = Literal["direct", "all"]
DirectionQuery = Literal["upstream", "downstream", "both"]

app = FastAPI(title="LineageHub", version="0.3.0")


def _store() -> MetadataStore:
    return MetadataStore(default_db_path())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/validation")
def metadata_validation() -> dict[str, Any]:
    store = _store()
    return validate_metadata(store)


@app.get("/graph/cycles")
def graph_cycles() -> dict[str, Any]:
    store = _store()
    return graph_cycles_for_store(store)


@app.get("/graph/edges/{dataset_name}")
def graph_edges_for_dataset(
    dataset_name: str,
    direction: DirectionQuery = Query("downstream", description="upstream | downstream | both"),
    depth: DepthQuery = Query("all", description="direct: one hop from root; all: edges inside transitive closure"),
) -> dict[str, Any]:
    store = _store()
    try:
        return graph_edges_json(store, dataset_name, direction=direction, depth=depth)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/export/lineage")
def export_lineage() -> dict[str, Any]:
    store = _store()
    return lineage_export_payload(store)


@app.get("/export/incidents")
def export_incidents(
    ranked: bool = Query(False, description="If true, emit incident_ranking instead of incident_summary"),
    status: str = Query("failed", description="Run status filter"),
    since: Optional[str] = Query(None, description="Only runs with started_at >= since"),
    limit: Optional[int] = Query(None, ge=1, description="For summary: max runs evaluated; for ranked: max ranked rows"),
    limit_runs: Optional[int] = Query(
        None,
        ge=1,
        description="Ranked only: max failed runs evaluated before ranking (ignored for summary)",
    ),
) -> dict[str, Any]:
    store = _store()
    return export_incidents_payload(
        store,
        ranked=ranked,
        status=status,
        since=since,
        limit=limit,
        limit_runs=limit_runs,
    )


@app.get("/datasets")
def list_datasets() -> dict[str, Any]:
    store = _store()
    return datasets_list_payload(store.list_dataset_records())


@app.get("/datasets/{name}")
def dataset_detail(name: str) -> dict[str, Any]:
    store = _store()
    try:
        return dataset_show_for_name(store, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/datasets/{name}/upstream")
def dataset_upstream(
    name: str,
    depth: DepthQuery = Query("all", description="direct: one hop; all: transitive closure"),
) -> dict[str, Any]:
    store = _store()
    try:
        return upstream_for_dataset(store, name, depth=depth)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/datasets/{name}/downstream")
def dataset_downstream(
    name: str,
    depth: DepthQuery = Query("all", description="direct: one hop; all: transitive closure"),
) -> dict[str, Any]:
    store = _store()
    try:
        return downstream_for_dataset(store, name, depth=depth)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/datasets/{name}/impact")
def dataset_impact(name: str) -> dict[str, Any]:
    store = _store()
    try:
        return impact_for_dataset(store, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/incidents/summary")
def incidents_summary(
    status: str = Query("failed", description="Run status filter"),
    since: Optional[str] = Query(None, description="Only runs with started_at >= since"),
    limit: Optional[int] = Query(None, ge=1, description="Max runs evaluated"),
) -> dict[str, Any]:
    store = _store()
    return incidents_summary_for_store(store, status=status, since=since, limit=limit)


@app.get("/incidents/rank")
def incidents_rank(
    status: str = Query("failed", description="Run status filter"),
    since: Optional[str] = Query(None, description="Only runs with started_at >= since"),
    limit: Optional[int] = Query(None, ge=1, description="Max ranked incidents returned"),
    limit_runs: Optional[int] = Query(
        None,
        ge=1,
        description="Max failed runs evaluated before ranking (feeds summarize step)",
    ),
) -> dict[str, Any]:
    store = _store()
    return incidents_rank_for_store(
        store,
        status=status,
        since=since,
        limit_runs=limit_runs,
        limit_ranked=limit,
    )


@app.get("/runs")
def list_runs(
    status: Optional[str] = Query(None, description="Filter by run status"),
    job: Optional[str] = Query(None, description="Filter by job name"),
    since: Optional[str] = Query(None, description="Only runs with started_at >= since (ISO-8601)"),
    limit: Optional[int] = Query(None, ge=1, description="Max number of rows"),
) -> dict[str, Any]:
    store = _store()
    rows = store.list_runs(status=status, job_name=job, since=since, limit=limit)
    return runs_list_payload(rows, status=status, job=job, since=since, limit=limit)


@app.get("/jobs")
def list_jobs() -> dict[str, Any]:
    store = _store()
    return jobs_list_payload(store.list_jobs())


@app.get("/jobs/{job_name}")
def job_detail(job_name: str) -> dict[str, Any]:
    store = _store()
    try:
        return job_show_for_name(store, job_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/jobs/{job_name}/runs/latest")
def latest_run_for_job(job_name: str) -> dict[str, Any]:
    store = _store()
    latest = store.get_latest_run(job_name)
    return latest_run_payload(job_name, latest)


@app.get("/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    store = _store()
    try:
        return run_show_for_run_id(store, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/runs/{run_id}/impact")
def run_impact(run_id: str) -> dict[str, Any]:
    store = _store()
    try:
        return run_impact_for_run_id(store, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
