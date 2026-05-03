"""Tests for lineage graph traversal."""

from __future__ import annotations

import pytest

from lineagehub.graph import (
    collect_graph_edges,
    get_direct_downstream,
    get_direct_upstream,
    get_downstream,
    get_upstream,
    impact_analysis,
    lineage_downstream_results,
    lineage_upstream_results,
)
from lineagehub.store import MetadataStore


def test_upstream_transitive_order(sample_store: MetadataStore) -> None:
    assert get_upstream(sample_store, "mart_daily_sales") == ["clean_orders", "raw_orders"]


def test_downstream_transitive_order(sample_store: MetadataStore) -> None:
    assert get_downstream(sample_store, "raw_orders") == [
        "clean_orders",
        "mart_daily_sales",
        "sales_dashboard",
    ]


def test_impact_matches_downstream(sample_store: MetadataStore) -> None:
    assert impact_analysis(sample_store, "raw_orders") == get_downstream(
        sample_store, "raw_orders"
    )


def test_unknown_dataset_raises(sample_store: MetadataStore) -> None:
    with pytest.raises(ValueError, match="Unknown dataset"):
        get_upstream(sample_store, "no_such_table")


def test_leaf_upstream_empty(sample_store: MetadataStore) -> None:
    assert get_upstream(sample_store, "raw_orders") == []


def test_sink_downstream_empty(sample_store: MetadataStore) -> None:
    assert get_downstream(sample_store, "sales_dashboard") == []


def test_direct_upstream_single_hop(sample_store: MetadataStore) -> None:
    assert get_direct_upstream(sample_store, "mart_daily_sales") == ["clean_orders"]


def test_direct_downstream_single_hop(sample_store: MetadataStore) -> None:
    assert get_direct_downstream(sample_store, "raw_orders") == ["clean_orders"]


def test_lineage_upstream_includes_distances(sample_store: MetadataStore) -> None:
    rows = lineage_upstream_results(sample_store, "mart_daily_sales", depth="all")
    assert [(r.name, r.distance) for r in rows] == [("clean_orders", 1), ("raw_orders", 2)]


def test_lineage_downstream_direct_distances(sample_store: MetadataStore) -> None:
    rows = lineage_downstream_results(sample_store, "raw_orders", depth="direct")
    assert [(r.name, r.distance) for r in rows] == [("clean_orders", 1)]


def test_collect_graph_edges_downstream_transitive(sample_store: MetadataStore) -> None:
    edges = collect_graph_edges(sample_store, "raw_orders", direction="downstream", depth="all")
    assert ("raw_orders", "clean_orders") in edges
    assert ("clean_orders", "mart_daily_sales") in edges
    assert ("mart_daily_sales", "sales_dashboard") in edges


def test_collect_graph_edges_upstream_direct(sample_store: MetadataStore) -> None:
    edges = collect_graph_edges(
        sample_store, "mart_daily_sales", direction="upstream", depth="direct"
    )
    assert edges == [("clean_orders", "mart_daily_sales")]
