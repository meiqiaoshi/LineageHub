"""FastAPI read-only service tests (requires optional ``api`` extras)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LINEAGE_JSON = REPO_ROOT / "examples" / "sample_lineage.json"
SAMPLE_RUNS_JSON = REPO_ROOT / "examples" / "sample_runs.json"


@pytest.fixture()
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from lineagehub.api import app
    from lineagehub.loader import load_lineage_json, load_runs_json
    from lineagehub.store import MetadataStore

    db = tmp_path / "api.sqlite"
    monkeypatch.setenv("LINEAGEHUB_DB", str(db))
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    load_runs_json(store, SAMPLE_RUNS_JSON)
    return TestClient(app)


def test_health(api_client) -> None:
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_datasets(api_client) -> None:
    r = api_client.get("/datasets")
    assert r.status_code == 200
    names = {row["name"] for row in r.json()}
    assert names == {"raw_orders", "clean_orders", "mart_daily_sales", "sales_dashboard"}


def test_upstream_depth_all(api_client) -> None:
    r = api_client.get("/datasets/mart_daily_sales/upstream")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "upstream"
    assert [d["name"] for d in body["datasets"]] == ["clean_orders", "raw_orders"]


def test_downstream_direct(api_client) -> None:
    r = api_client.get("/datasets/raw_orders/downstream", params={"depth": "direct"})
    assert r.status_code == 200
    assert r.json()["datasets"] == [{"name": "clean_orders", "distance": 1}]


def test_unknown_dataset_404(api_client) -> None:
    r = api_client.get("/datasets/nope/upstream")
    assert r.status_code == 404


def test_run_impact(api_client) -> None:
    r = api_client.get("/runs/run_001/impact")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "run_impact"
    assert body["job"] == "clean_orders_job"
    assert body["affected_count"] == 2
