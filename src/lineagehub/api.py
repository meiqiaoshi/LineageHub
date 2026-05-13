"""Read-only FastAPI service for lineage queries (optional dependency group ``api``)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Query

from lineagehub.analysis import incident_ranking, summarize_failed_runs
from lineagehub.db_path import default_db_path
from lineagehub.graph import (
    analyze_run_impact,
    collect_graph_edges,
    find_cycles,
    lineage_downstream_results,
    lineage_impact_results,
    lineage_upstream_results,
)
from lineagehub.output import (
    dataset_catalog_row,
    dataset_show_payload,
    downstream_payload,
    graph_cycles_payload,
    graph_edges_payload,
    impact_payload,
    job_show_payload,
    lineage_export_payload,
    run_impact_payload,
    upstream_payload,
)
from lineagehub.store import MetadataStore, RunRecord
from lineagehub.validation import validate_metadata

DepthQuery = Literal["direct", "all"]
DirectionQuery = Literal["upstream", "downstream", "both"]

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


@app.get("/validation")
def metadata_validation() -> dict[str, Any]:
    store = _store()
    return validate_metadata(store)


@app.get("/graph/cycles")
def graph_cycles() -> dict[str, Any]:
    store = _store()
    return graph_cycles_payload(find_cycles(store))


@app.get("/graph/edges/{dataset_name}")
def graph_edges_for_dataset(
    dataset_name: str,
    direction: DirectionQuery = Query("downstream", description="upstream | downstream | both"),
    depth: DepthQuery = Query("all", description="direct: one hop from root; all: edges inside transitive closure"),
) -> dict[str, Any]:
    store = _store()
    try:
        edges = collect_graph_edges(store, dataset_name, direction=direction, depth=depth)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return graph_edges_payload(dataset_name, direction, depth, edges)


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
) -> dict[str, Any]:
    store = _store()
    if ranked:
        return incident_ranking(
            store,
            status=status,
            since=since,
            limit_runs=None,
            limit_ranked=limit,
        )
    return summarize_failed_runs(store, status=status, since=since, limit=limit)


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


@app.get("/datasets/{name}")
def dataset_detail(name: str) -> dict[str, Any]:
    store = _store()
    ds = store.get_dataset_by_name(name)
    if ds is None or ds.dataset_id is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {name!r}")
    upstream_items = lineage_upstream_results(store, name, depth="all")
    downstream_items = lineage_downstream_results(store, name, depth="all")
    producers = store.list_job_names_producing_dataset(ds.dataset_id)
    consumers = store.list_job_names_consuming_dataset(ds.dataset_id)
    return dataset_show_payload(
        name=name,
        dataset_type=ds.dataset_type,
        uri=ds.uri,
        producer_jobs=producers,
        consumer_jobs=consumers,
        upstream=upstream_items,
        downstream=downstream_items,
        owner=ds.owner,
        description=ds.description,
        tags=ds.tags,
        criticality=ds.criticality,
        system=ds.system,
    )


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
    since: Optional[str] = Query(None, description="Only runs with started_at >= since"),
    limit: Optional[int] = Query(None, ge=1, description="Max runs evaluated"),
) -> dict[str, Any]:
    store = _store()
    return summarize_failed_runs(store, status=status, since=since, limit=limit)


@app.get("/incidents/rank")
def incidents_rank(
    status: str = Query("failed", description="Run status filter"),
    since: Optional[str] = Query(None, description="Only runs with started_at >= since"),
    limit: Optional[int] = Query(None, ge=1, description="Max ranked incidents returned"),
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
    status: Optional[str] = Query(None, description="Filter by run status"),
    job: Optional[str] = Query(None, description="Filter by job name"),
    since: Optional[str] = Query(None, description="Only runs with started_at >= since (ISO-8601)"),
    limit: Optional[int] = Query(None, ge=1, description="Max number of rows"),
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


@app.get("/jobs")
def list_jobs() -> dict[str, Any]:
    store = _store()
    rows = store.list_jobs()
    return {
        "query_type": "jobs_list",
        "count": len(rows),
        "jobs": [{"name": r.name, "description": r.description} for r in rows],
    }


@app.get("/jobs/{job_name}")
def job_detail(job_name: str) -> dict[str, Any]:
    store = _store()
    job = store.get_job_by_name(job_name)
    if job is None or job.job_id is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name!r}")
    inputs = store.list_input_dataset_names_for_job(job.job_id)
    outputs = store.list_output_dataset_names_for_job(job.job_id)
    latest = store.get_latest_run(job_name)
    run_count = store.count_runs_for_job(job.job_id)
    latest_json = None
    if latest is not None:
        rid = latest.external_run_id if latest.external_run_id is not None else str(latest.internal_run_id)
        latest_json = {"run_id": rid, "status": latest.status}
    return job_show_payload(
        name=job.name,
        description=job.description,
        inputs=inputs,
        outputs=outputs,
        latest_run=latest_json,
        run_count=run_count,
    )


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
