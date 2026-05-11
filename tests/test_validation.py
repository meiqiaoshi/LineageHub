"""Tests for ``lineagehub.validation.validate_metadata``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.models import Dataset, Job
from lineagehub.store import MetadataStore, utc_now_iso
from lineagehub.validation import validate_metadata

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LINEAGE_JSON = REPO_ROOT / "examples" / "sample_lineage.json"


def test_validation_clean_sample_lineage(sample_store: MetadataStore) -> None:
    out = validate_metadata(sample_store)
    assert out["query_type"] == "metadata_validation"
    assert out["status"] == "pass"
    assert out["error_count"] == 0
    assert out["errors"] == []
    assert out["warning_count"] == 0
    assert out["warnings"] == []


def test_validation_isolated_dataset_warning(sample_store: MetadataStore) -> None:
    sample_store.upsert_dataset(Dataset(name="temp_debug_table"))
    out = validate_metadata(sample_store)
    assert out["status"] == "pass"
    assert out["error_count"] == 0
    codes = {w["code"] for w in out["warnings"]}
    assert "isolated_dataset" in codes
    lonely = next(w for w in out["warnings"] if w["code"] == "isolated_dataset")
    assert lonely["dataset"] == "temp_debug_table"


def test_validation_job_without_lineage_warning(sample_store: MetadataStore) -> None:
    sample_store.upsert_job(Job(name="ghost_etl_job"))
    out = validate_metadata(sample_store)
    assert out["status"] == "pass"
    ghost = next(w for w in out["warnings"] if w["code"] == "job_no_lineage_io" and w["job"] == "ghost_etl_job")
    assert ghost["input_dataset_count"] == 0
    assert ghost["output_dataset_count"] == 0


def test_validation_missing_job_on_edge(tmp_path: Path) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    conn = store.connect()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        up = conn.execute(
            "SELECT dataset_id FROM datasets WHERE name = ?", ("raw_orders",)
        ).fetchone()
        down = conn.execute(
            "SELECT dataset_id FROM datasets WHERE name = ?", ("clean_orders",)
        ).fetchone()
        assert up and down
        conn.execute(
            """INSERT INTO lineage_edges
               (upstream_dataset_id, downstream_dataset_id, job_id, created_at)
               VALUES (?, ?, ?, ?)""",
            (int(up["dataset_id"]), int(down["dataset_id"]), 888_888, utc_now_iso()),
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

    out = validate_metadata(store)
    assert out["status"] == "fail"
    err = next(e for e in out["errors"] if e["code"] == "missing_job_reference")
    assert err["job_id"] == 888_888


def test_validation_missing_downstream_dataset_on_edge(tmp_path: Path) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    conn = store.connect()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        up = conn.execute(
            "SELECT dataset_id FROM datasets WHERE name = ?", ("raw_orders",)
        ).fetchone()
        jid = conn.execute("SELECT job_id FROM jobs WHERE name = ?", ("clean_orders_job",)).fetchone()
        assert up and jid
        conn.execute(
            """INSERT INTO lineage_edges
               (upstream_dataset_id, downstream_dataset_id, job_id, created_at)
               VALUES (?, ?, ?, ?)""",
            (int(up["dataset_id"]), 999_999, int(jid["job_id"]), utc_now_iso()),
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

    out = validate_metadata(store)
    assert out["status"] == "fail"
    assert out["error_count"] >= 1
    err = next(e for e in out["errors"] if e["code"] == "missing_dataset_reference")
    assert err["side"] == "downstream"
    assert err["dataset_id"] == 999_999


def test_validation_run_unknown_job(tmp_path: Path) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    conn = store.connect()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            """INSERT INTO runs (job_id, status, started_at, ended_at, error_message, external_run_id)
               VALUES (?, ?, NULL, NULL, NULL, ?)""",
            (99_999, "failed", "orphan_run"),
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

    out = validate_metadata(store)
    assert out["status"] == "fail"
    err = next(e for e in out["errors"] if e["code"] == "run_unknown_job")
    assert err["job_id"] == 99_999


def test_validation_duplicate_external_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "dup_ext",
                        "job_name": "clean_orders_job",
                        "status": "failed",
                        "started_at": "2026-05-01T09:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)
    conn = store.connect()
    try:
        conn.execute("DROP INDEX IF EXISTS idx_runs_external_run_id")
        conn.execute("PRAGMA foreign_keys = OFF")
        jid = conn.execute("SELECT job_id FROM jobs WHERE name = ?", ("daily_sales_job",)).fetchone()
        assert jid
        conn.execute(
            """INSERT INTO runs (job_id, status, started_at, ended_at, error_message, external_run_id)
               VALUES (?, ?, NULL, NULL, NULL, ?)""",
            (int(jid["job_id"]), "failed", "dup_ext"),
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

    # Avoid recreating the unique index while duplicate rows exist (would raise).
    monkeypatch.setattr("lineagehub.validation._apply_runs_migrations", lambda _c: None)

    out = validate_metadata(store)
    assert out["status"] == "fail"
    dup = next(e for e in out["errors"] if e["code"] == "duplicate_external_run_id")
    assert dup["external_run_id"] == "dup_ext"
    assert dup["count"] == 2


def test_validation_empty_store_passes(empty_store: MetadataStore) -> None:
    out = validate_metadata(empty_store)
    assert out["status"] == "pass"
    assert out["errors"] == []
    assert out["warnings"] == []
