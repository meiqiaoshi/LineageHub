"""Graph export formatter tests."""

from __future__ import annotations

from lineagehub.output import format_edges_dot, format_edges_mermaid, format_edges_text


def test_format_edges_text() -> None:
    edges = [("a", "b"), ("b", "c")]
    assert format_edges_text(edges) == "a -> b\nb -> c\n"


def test_format_edges_mermaid_contains_graph_td() -> None:
    out = format_edges_mermaid([("raw_orders", "clean_orders")])
    assert "graph TD" in out
    assert "-->" in out


def test_format_edges_dot_digraph() -> None:
    out = format_edges_dot([("x", "y")])
    assert "digraph lineage" in out
    assert "->" in out
