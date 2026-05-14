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


def test_metadata_validation(api_client) -> None:
    r = api_client.get("/validation")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "metadata_validation"
    assert body["status"] == "pass"


def test_graph_cycles(api_client) -> None:
    r = api_client.get("/graph/cycles")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "graph_cycles"
    assert body["cycle_count"] == 0
    assert body["cycles"] == []


def test_graph_edges_downstream_all(api_client) -> None:
    r = api_client.get("/graph/edges/raw_orders", params={"direction": "downstream", "depth": "all"})
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "graph_edges"
    assert body["dataset"] == "raw_orders"
    assert body["direction"] == "downstream"
    assert body["depth"] == "all"
    pairs = {(e["upstream"], e["downstream"]) for e in body["edges"]}
    assert ("raw_orders", "clean_orders") in pairs
    assert ("clean_orders", "mart_daily_sales") in pairs
    assert ("mart_daily_sales", "sales_dashboard") in pairs


def test_graph_edges_unknown_dataset(api_client) -> None:
    r = api_client.get("/graph/edges/unknown_dataset_xyz")
    assert r.status_code == 404


def test_export_lineage(api_client) -> None:
    r = api_client.get("/export/lineage")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "lineage_export"
    assert {d["name"] for d in body["datasets"]} == {
        "raw_orders",
        "clean_orders",
        "mart_daily_sales",
        "sales_dashboard",
    }


def test_export_incidents(api_client) -> None:
    r = api_client.get("/export/incidents")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "incident_summary"
    assert body["incident_count"] == 2


def test_export_incidents_ranked_limit(api_client) -> None:
    r = api_client.get("/export/incidents", params={"ranked": "true", "limit": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "incident_ranking"
    assert len(body["incidents"]) == 1


def test_list_datasets(api_client) -> None:
    r = api_client.get("/datasets")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "datasets_list"
    assert body["count"] == 4
    rows = body["datasets"]
    names = {row["name"] for row in rows}
    assert names == {"raw_orders", "clean_orders", "mart_daily_sales", "sales_dashboard"}
    mart = next(x for x in rows if x["name"] == "mart_daily_sales")
    assert mart["owner"] == "analytics-engineering"
    assert mart["criticality"] == "high"
    assert mart["tags"] == ["gold", "finance", "aggregates"]


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


def test_dataset_detail(api_client) -> None:
    r = api_client.get("/datasets/mart_daily_sales")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "dataset_show"
    assert body["dataset"]["name"] == "mart_daily_sales"
    assert body["dataset"]["criticality"] == "high"
    assert [d["name"] for d in body["upstream"]] == ["clean_orders", "raw_orders"]
    assert [d["name"] for d in body["downstream"]] == ["sales_dashboard"]
    assert "daily_sales_job" in body["producer_jobs"]


def test_dataset_detail_unknown(api_client) -> None:
    r = api_client.get("/datasets/unknown_dataset_xyz")
    assert r.status_code == 404


def test_jobs_list(api_client) -> None:
    r = api_client.get("/jobs")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "jobs_list"
    names = {j["name"] for j in body["jobs"]}
    assert names == {"clean_orders_job", "daily_sales_job", "sales_dashboard_refresh"}
    for j in body["jobs"]:
        assert j["system"] is None


def test_job_detail(api_client) -> None:
    r = api_client.get("/jobs/clean_orders_job")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "job_show"
    assert body["job"]["name"] == "clean_orders_job"
    assert body["job"]["system"] is None
    assert body["inputs"] == ["raw_orders"]
    assert body["outputs"] == ["clean_orders"]
    assert body["run_count"] == 1
    assert body["latest_run"] == {
        "run_id": "run_001",
        "job_name": "clean_orders_job",
        "status": "failed",
        "started_at": "2026-05-01T09:00:00Z",
        "ended_at": "2026-05-01T09:03:00Z",
        "error_message": "Source dataset raw_orders was stale",
    }


def test_job_detail_unknown(api_client) -> None:
    r = api_client.get("/jobs/nonexistent_job_xyz")
    assert r.status_code == 404


def test_run_impact(api_client) -> None:
    r = api_client.get("/runs/run_001/impact")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "run_impact"
    assert body["job"] == "clean_orders_job"
    assert body["affected_count"] == 2


def test_run_detail(api_client) -> None:
    r = api_client.get("/runs/run_001")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "run_show"
    assert body["run"]["run_id"] == "run_001"
    assert body["run"]["job_name"] == "clean_orders_job"
    assert body["run"]["error_message"] == "Source dataset raw_orders was stale"


def test_run_detail_internal_id(api_client) -> None:
    r = api_client.get("/runs/1")
    assert r.status_code == 200
    assert r.json()["run"]["run_id"] == "run_001"


def test_run_detail_unknown(api_client) -> None:
    assert api_client.get("/runs/nonexistent_run_xyz").status_code == 404


def test_api_list_runs(api_client) -> None:
    r = api_client.get("/runs")
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "runs_list"
    assert [row["run_id"] for row in body["runs"]] == ["run_003", "run_002", "run_001"]


def test_api_list_runs_status_failed(api_client) -> None:
    r = api_client.get("/runs", params={"status": "failed"})
    assert r.status_code == 200
    body = r.json()
    assert body["filters"]["status"] == "failed"
    assert [row["run_id"] for row in body["runs"]] == ["run_003", "run_001"]


def test_api_list_runs_includes_error_message(api_client) -> None:
    r = api_client.get("/runs", params={"status": "failed"})
    assert r.status_code == 200
    by_id = {row["run_id"]: row for row in r.json()["runs"]}
    assert by_id["run_001"]["error_message"] == "Source dataset raw_orders was stale"
    assert by_id["run_003"]["error_message"] is None


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


def test_api_incidents_rank_limit_runs(api_client) -> None:
    r = api_client.get("/incidents/rank", params={"limit_runs": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "incident_ranking"
    assert len(body["incidents"]) == 1
    assert body["incidents"][0]["run_id"] == "run_003"


def test_export_incidents_ranked_limit_runs(api_client) -> None:
    r = api_client.get("/export/incidents", params={"ranked": "true", "limit_runs": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["query_type"] == "incident_ranking"
    assert len(body["incidents"]) == 1
    assert body["incidents"][0]["run_id"] == "run_003"
