"""Read-only FastAPI service for lineage queries (optional dependency group ``api``)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query

from lineagehub.cli import default_db_path
from lineagehub.graph import (
    analyze_run_impact,
    lineage_downstream_results,
    lineage_impact_results,
    lineage_upstream_results,
)
from lineagehub.output import (
    downstream_payload,
    impact_payload,
    run_impact_payload,
    upstream_payload,
)
from lineagehub.store import MetadataStore

DepthQuery = Literal["direct", "all"]

app = FastAPI(title="LineageHub", version="0.2.0")


def _store() -> MetadataStore:
    return MetadataStore(default_db_path())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/datasets")
def list_datasets() -> list[dict[str, Any]]:
    store = _store()
    return [
        {"name": d.name, "type": d.dataset_type, "uri": d.uri} for d in store.list_datasets()
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


@app.get("/runs/{run_id}/impact")
def run_impact(run_id: str) -> dict[str, Any]:
    store = _store()
    try:
        analysis = analyze_run_impact(store, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return run_impact_payload(analysis)
