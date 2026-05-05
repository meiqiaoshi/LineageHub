from __future__ import annotations

from lineagehub.models import Run
from lineagehub.store import MetadataStore


def _insert_run(
    store: MetadataStore,
    *,
    external_run_id: str,
    job_name: str,
    status: str,
    started_at: str | None,
) -> None:
    job = store.get_job_by_name(job_name)
    assert job is not None and job.job_id is not None
    store.insert_run(
        Run(
            job_id=job.job_id,
            status=status,
            external_run_id=external_run_id,
            started_at=started_at,
        )
    )


def test_list_runs_all(sample_store: MetadataStore) -> None:
    _insert_run(
        sample_store,
        external_run_id="r1",
        job_name="clean_orders_job",
        status="failed",
        started_at="2026-05-01T09:00:00Z",
    )
    _insert_run(
        sample_store,
        external_run_id="r2",
        job_name="daily_sales_job",
        status="success",
        started_at="2026-05-01T10:00:00Z",
    )
    rows = sample_store.list_runs()
    assert [r.external_run_id for r in rows] == ["r2", "r1"]


def test_list_runs_filter_status(sample_store: MetadataStore) -> None:
    _insert_run(
        sample_store,
        external_run_id="r1",
        job_name="clean_orders_job",
        status="failed",
        started_at="2026-05-01T09:00:00Z",
    )
    _insert_run(
        sample_store,
        external_run_id="r2",
        job_name="clean_orders_job",
        status="success",
        started_at="2026-05-01T10:00:00Z",
    )
    rows = sample_store.list_runs(status="failed")
    assert [r.external_run_id for r in rows] == ["r1"]
    assert rows[0].status == "failed"


def test_list_runs_filter_job_name(sample_store: MetadataStore) -> None:
    _insert_run(
        sample_store,
        external_run_id="r1",
        job_name="clean_orders_job",
        status="failed",
        started_at="2026-05-01T09:00:00Z",
    )
    _insert_run(
        sample_store,
        external_run_id="r2",
        job_name="daily_sales_job",
        status="failed",
        started_at="2026-05-01T10:00:00Z",
    )
    rows = sample_store.list_runs(job_name="clean_orders_job")
    assert [r.external_run_id for r in rows] == ["r1"]
    assert rows[0].job_name == "clean_orders_job"


def test_list_runs_limit(sample_store: MetadataStore) -> None:
    _insert_run(
        sample_store,
        external_run_id="r1",
        job_name="clean_orders_job",
        status="failed",
        started_at="2026-05-01T09:00:00Z",
    )
    _insert_run(
        sample_store,
        external_run_id="r2",
        job_name="daily_sales_job",
        status="failed",
        started_at="2026-05-01T10:00:00Z",
    )
    _insert_run(
        sample_store,
        external_run_id="r3",
        job_name="sales_dashboard_refresh",
        status="failed",
        started_at="2026-05-01T11:00:00Z",
    )
    rows = sample_store.list_runs(limit=2)
    assert [r.external_run_id for r in rows] == ["r3", "r2"]


def test_list_runs_newest_first(sample_store: MetadataStore) -> None:
    _insert_run(
        sample_store,
        external_run_id="r_old",
        job_name="clean_orders_job",
        status="failed",
        started_at="2026-05-01T09:00:00Z",
    )
    _insert_run(
        sample_store,
        external_run_id="r_new",
        job_name="clean_orders_job",
        status="failed",
        started_at="2026-05-01T12:00:00Z",
    )
    rows = sample_store.list_runs()
    assert [r.external_run_id for r in rows] == ["r_new", "r_old"]


def test_get_latest_run_picks_newest_started_at(sample_store: MetadataStore) -> None:
    _insert_run(
        sample_store,
        external_run_id="r_old",
        job_name="clean_orders_job",
        status="failed",
        started_at="2026-05-01T09:00:00Z",
    )
    _insert_run(
        sample_store,
        external_run_id="r_new",
        job_name="clean_orders_job",
        status="success",
        started_at="2026-05-01T12:00:00Z",
    )
    latest = sample_store.get_latest_run("clean_orders_job")
    assert latest is not None
    assert latest.external_run_id == "r_new"
    assert latest.status == "success"


def test_get_latest_run_same_started_at_tiebreak_by_internal_id(sample_store: MetadataStore) -> None:
    ts = "2026-05-01T12:00:00Z"
    _insert_run(
        sample_store,
        external_run_id="r_first",
        job_name="clean_orders_job",
        status="failed",
        started_at=ts,
    )
    _insert_run(
        sample_store,
        external_run_id="r_second",
        job_name="clean_orders_job",
        status="success",
        started_at=ts,
    )
    latest = sample_store.get_latest_run("clean_orders_job")
    assert latest is not None
    assert latest.external_run_id == "r_second"


def test_get_latest_run_job_has_no_runs(sample_store: MetadataStore) -> None:
    assert sample_store.get_latest_run("clean_orders_job") is None


def test_get_latest_run_unknown_job(sample_store: MetadataStore) -> None:
    assert sample_store.get_latest_run("nonexistent_job_xyz") is None

