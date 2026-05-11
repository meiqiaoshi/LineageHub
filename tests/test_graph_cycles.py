"""Tests for ``lineagehub.graph.find_cycles``."""

from __future__ import annotations

from pathlib import Path

from lineagehub.graph import find_cycles
from lineagehub.loader import load_lineage_json
from lineagehub.models import Dataset, LineageEdge
from lineagehub.store import MetadataStore

SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def test_find_cycles_sample_lineage_acyclic(sample_store: MetadataStore) -> None:
    assert find_cycles(sample_store) == []


def test_find_cycles_empty_graph(empty_store: MetadataStore) -> None:
    assert find_cycles(empty_store) == []


def test_find_cycles_simple_two_node_cycle(empty_store: MetadataStore) -> None:
    a = empty_store.upsert_dataset(Dataset(name="alpha"))
    b = empty_store.upsert_dataset(Dataset(name="beta"))
    empty_store.insert_lineage_edge(
        LineageEdge(upstream_dataset_id=a, downstream_dataset_id=b, job_id=None)
    )
    empty_store.insert_lineage_edge(
        LineageEdge(upstream_dataset_id=b, downstream_dataset_id=a, job_id=None)
    )
    assert find_cycles(empty_store) == [["alpha", "beta", "alpha"]]


def test_find_cycles_longer_cycle(empty_store: MetadataStore) -> None:
    a = empty_store.upsert_dataset(Dataset(name="A"))
    b = empty_store.upsert_dataset(Dataset(name="B"))
    c = empty_store.upsert_dataset(Dataset(name="C"))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=a, downstream_dataset_id=b, job_id=None))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=b, downstream_dataset_id=c, job_id=None))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=c, downstream_dataset_id=a, job_id=None))
    assert find_cycles(empty_store) == [["A", "B", "C", "A"]]


def test_find_cycles_disconnected_acyclic(empty_store: MetadataStore) -> None:
    a = empty_store.upsert_dataset(Dataset(name="x"))
    b = empty_store.upsert_dataset(Dataset(name="y"))
    c = empty_store.upsert_dataset(Dataset(name="p"))
    d = empty_store.upsert_dataset(Dataset(name="q"))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=a, downstream_dataset_id=b, job_id=None))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=c, downstream_dataset_id=d, job_id=None))
    assert find_cycles(empty_store) == []


def test_find_cycles_two_components_each_with_cycle(empty_store: MetadataStore) -> None:
    a1 = empty_store.upsert_dataset(Dataset(name="a1"))
    a2 = empty_store.upsert_dataset(Dataset(name="a2"))
    b1 = empty_store.upsert_dataset(Dataset(name="b1"))
    b2 = empty_store.upsert_dataset(Dataset(name="b2"))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=a1, downstream_dataset_id=a2, job_id=None))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=a2, downstream_dataset_id=a1, job_id=None))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=b1, downstream_dataset_id=b2, job_id=None))
    empty_store.insert_lineage_edge(LineageEdge(upstream_dataset_id=b2, downstream_dataset_id=b1, job_id=None))
    out = find_cycles(empty_store)
    assert out == [["a1", "a2", "a1"], ["b1", "b2", "b1"]]


def test_find_cycles_load_json_then_no_cycle(tmp_path: Path) -> None:
    db = tmp_path / "g.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE)
    assert find_cycles(store) == []
