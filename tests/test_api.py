"""FastAPI read-only service tests (requires optional ``api`` extras)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LINEAGE_JSON = REPO_ROOT / "examples" / "sample_lineage.json"


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
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_001",
                        "job_name": "clean_orders_job",
                        "status": "failed",
                        "started_at": "2026-05-01T09:00:00Z",
                        "ended_at": "2026-05-01T09:03:00Z",
                        "error_message": "Source dataset raw_orders was stale",
                    },
                    {
                        "run_id": "run_002",
                        "job_name": "daily_sales_job",
                        "status": "success",
                        "started_at": "2026-05-02T10:00:00Z",
                        "ended_at": "2026-05-02T10:05:00Z",
                    },
                    {
                        "run_id": "run_003",
                        "job_name": "daily_sales_job",
                        "status": "failed",
                        "started_at": "2026-05-03T08:00:00Z",
                        "ended_at": "2026-05-03T08:05:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)
    return TestClient(app)


def test_health(api_client) -> None:
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_datasets(api_client) -> None:
    r = api_client.get("/datasets")
    assert r.status_code == 200
    body = r.json()
    names = {row["name"] for row in body}
    assert names == {"raw_orders", "clean_orders", "mart_daily_sales", "sales_dashboard"}
    mart = next(x for x in body if x["name"] == "mart_daily_sales")
    assert "owner" in mart and mart["owner"] is None
    assert "tags" in mart and mart["tags"] is None


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


def test_api_list_runs(api_client) -> None:
    r = api_client.get("/runs")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "runs_list"
    assert [row["run_id"] for row in body["runs"]] == ["run_002", "run_001"]


def test_api_list_runs_status_failed(api_client) -> None:
    r = api_client.get("/runs", params={"status": "failed"})
    assert r.status_code == 200
    body = r.json()
    assert body["filters"]["status"] == "failed"
    assert [row["run_id"] for row in body["runs"]] == ["run_001"]


def test_api_jobs_latest_run(api_client) -> None:
    r = api_client.get("/jobs/daily_sales_job/runs/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "latest_run"
    assert body["job_name"] == "daily_sales_job"
    assert body["run"]["run_id"] == "run_003"


def test_api_jobs_latest_unknown_job(api_client) -> None:
    r = api_client.get("/jobs/nonexistent_job_xyz/runs/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["run"] is None


def test_api_incidents_summary(api_client) -> None:
    r = api_client.get("/incidents/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "incident_summary"
    assert body["scoring_method"] == "criticality_weighted"
    assert body["incident_count"] == 2
    assert {inc["run_id"] for inc in body["incidents"]} == {"run_001", "run_003"}
    assert all(inc["scoring_method"] == "criticality_weighted" for inc in body["incidents"])


def test_api_incidents_summary_limit(api_client) -> None:
    r = api_client.get("/incidents/summary", params={"limit": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["incident_count"] == 1
    assert body["incidents"][0]["run_id"] == "run_003"


def test_api_incidents_rank(api_client) -> None:
    r = api_client.get("/incidents/rank")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "incident_ranking"
    assert body["ranking_method"] == "criticality_weighted"
    ids = [row["run_id"] for row in body["incidents"]]
    assert ids == ["run_001", "run_003"]


def test_api_incidents_rank_limit(api_client) -> None:
    r = api_client.get("/incidents/rank", params={"limit": 1})
    assert r.status_code == 200
    body = r.json()
    assert len(body["incidents"]) == 1
    assert body["incidents"][0]["run_id"] == "run_001"
