"""Structured JSON payloads and graph export formatters."""

from __future__ import annotations

import json
import re
from typing import Any

from lineagehub.models import LineageResult


def dumps_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def upstream_payload(dataset: str, depth: str, items: list[LineageResult]) -> dict[str, Any]:
    return {
        "query_type": "upstream",
        "dataset": dataset,
        "depth": depth,
        "count": len(items),
        "datasets": [{"name": x.name, "distance": x.distance} for x in items],
    }


def downstream_payload(dataset: str, depth: str, items: list[LineageResult]) -> dict[str, Any]:
    return {
        "query_type": "downstream",
        "dataset": dataset,
        "depth": depth,
        "count": len(items),
        "datasets": [{"name": x.name, "distance": x.distance} for x in items],
    }


def impact_payload(dataset: str, items: list[LineageResult]) -> dict[str, Any]:
    return {
        "query_type": "impact",
        "dataset": dataset,
        "impact_type": "transitive_downstream",
        "affected_count": len(items),
        "affected_datasets": [{"name": x.name, "distance": x.distance} for x in items],
    }


def format_edges_text(edges: list[tuple[str, str]]) -> str:
    if not edges:
        return ""
    return "\n".join(f"{u} -> {v}" for u, v in edges) + "\n"


def format_edges_mermaid(edges: list[tuple[str, str]]) -> str:
    lines = ["graph TD"]
    for u, v in edges:
        uid = _mermaid_node_id(u)
        vid = _mermaid_node_id(v)
        lines.append(f"  {uid}[{_mermaid_label(u)}] --> {vid}[{_mermaid_label(v)}]")
    return "\n".join(lines) + "\n"


def format_edges_dot(edges: list[tuple[str, str]]) -> str:
    lines = ["digraph lineage {"]
    for u, v in edges:
        lines.append(f'  "{_dot_escape(u)}" -> "{_dot_escape(v)}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _mermaid_label(name: str) -> str:
    escaped = name.replace('"', "'")
    return f'"{escaped}"'


def _mermaid_node_id(name: str) -> str:
    slug = re.sub(r"\W+", "_", name)
    if not slug:
        return "node"
    if slug[0].isdigit():
        return "n_" + slug
    return slug


def _dot_escape(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')
