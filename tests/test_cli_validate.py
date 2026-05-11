"""CLI ``validate`` / ``doctor`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json
from lineagehub.models import Dataset
from lineagehub.store import MetadataStore, utc_now_iso

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def test_validate_text_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "validate"]) == 0
    out = capsys.readouterr().out
    assert "Metadata validation: PASS" in out
    assert "Warnings:" in out
    assert "Errors:" in out
    assert "- None" in out


def test_validate_doctor_alias(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "doctor"]) == 0
    assert "Metadata validation: PASS" in capsys.readouterr().out


def test_validate_text_warnings_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    store.upsert_dataset(Dataset(name="temp_debug_table"))
    assert main(["--db", str(db), "validate"]) == 0
    out = capsys.readouterr().out
    assert "Metadata validation: PASS" in out
    assert "isolated_dataset" in out
    assert "temp_debug_table" in out


def test_validate_text_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
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

    assert main(["--db", str(db), "validate"]) == 1
    out = capsys.readouterr().out
    assert "Metadata validation: FAIL" in out
    assert "missing_dataset_reference" in out


def test_validate_json_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "validate", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "metadata_validation"
    assert payload["status"] == "pass"


def test_validate_json_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "v.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
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

    assert main(["--db", str(db), "validate", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "fail"
    assert payload["error_count"] >= 1
