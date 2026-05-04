"""Tests for SQLite metadata store."""

from __future__ import annotations

import sqlite3

import pytest

from lineagehub.models import Dataset, Job, LineageEdge, Run
from lineagehub.store import MetadataStore


def test_init_schema_creates_tables(empty_store: MetadataStore) -> None:
    conn = empty_store.connect()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r["name"] for r in rows}
        assert {"datasets", "jobs", "runs", "lineage_edges"}.issubset(names)
    finally:
        conn.close()


def test_upsert_dataset_stable_id_and_roundtrip(empty_store: MetadataStore) -> None:
    id1 = empty_store.upsert_dataset(Dataset(name="orders", dataset_type="table", uri="x://o"))
    id2 = empty_store.upsert_dataset(Dataset(name="orders", dataset_type="file"))
    assert id1 == id2
    ds = empty_store.get_dataset_by_name("orders")
    assert ds is not None
    assert ds.dataset_id == id1
    assert ds.dataset_type == "file"
    assert ds.uri is None


def test_list_datasets_sorted_by_name(empty_store: MetadataStore) -> None:
    empty_store.upsert_dataset(Dataset(name="zebra"))
    empty_store.upsert_dataset(Dataset(name="alpha"))
    names = [d.name for d in empty_store.list_datasets()]
    assert names == ["alpha", "zebra"]


def test_insert_run_foreign_key(empty_store: MetadataStore) -> None:
    jid = empty_store.upsert_job(Job(name="j"))
    rid = empty_store.insert_run(Run(job_id=jid, status="success"))
    assert rid >= 1
    with pytest.raises(sqlite3.IntegrityError):
        empty_store.insert_run(Run(job_id=999999, status="failed"))


def test_insert_run_with_external_id_roundtrip(empty_store: MetadataStore) -> None:
    jid = empty_store.upsert_job(Job(name="job1"))
    empty_store.insert_run(
        Run(job_id=jid, status="success", external_run_id="ext-1", started_at="2026-01-01T00:00:00Z")
    )
    run = empty_store.get_run_by_external_id("ext-1")
    assert run is not None
    assert run.status == "success"
    assert run.external_run_id == "ext-1"


def test_lineage_edge_idempotent_and_foreign_keys(empty_store: MetadataStore) -> None:
    a = empty_store.upsert_dataset(Dataset(name="a"))
    b = empty_store.upsert_dataset(Dataset(name="b"))
    j = empty_store.upsert_job(Job(name="job"))
    e = LineageEdge(upstream_dataset_id=a, downstream_dataset_id=b, job_id=j)
    id1 = empty_store.insert_lineage_edge(e)
    id2 = empty_store.insert_lineage_edge(e)
    assert id1 == id2
    assert len(empty_store.list_lineage_edges()) == 1

    with pytest.raises(sqlite3.IntegrityError):
        empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=999, downstream_dataset_id=b))


def test_get_dataset_id_by_name(empty_store: MetadataStore) -> None:
    assert empty_store.get_dataset_id_by_name("missing") is None
    empty_store.upsert_dataset(Dataset(name="x"))
    assert empty_store.get_dataset_id_by_name("x") == 1
