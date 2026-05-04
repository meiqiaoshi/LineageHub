"""Tests for JSON run loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.loader import load_runs_json
from lineagehub.store import MetadataStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_RUNS_JSON = REPO_ROOT / "examples" / "sample_runs.json"


def test_load_runs_inserts_row(sample_store: MetadataStore) -> None:
    load_runs_json(sample_store, SAMPLE_RUNS_JSON)
    run = sample_store.get_run_by_external_id("run_001")
    assert run is not None
    assert run.status == "failed"
    assert run.error_message is not None


def test_load_runs_unknown_job(sample_store: MetadataStore, tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "x",
                        "job_name": "no_such_job",
                        "status": "failed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown job"):
        load_runs_json(sample_store, path)


def test_load_runs_duplicate_external_id(sample_store: MetadataStore) -> None:
    load_runs_json(sample_store, SAMPLE_RUNS_JSON)
    with pytest.raises(ValueError, match="duplicate"):
        load_runs_json(sample_store, SAMPLE_RUNS_JSON)
