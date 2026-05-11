"""Structured JSON payloads and graph export formatters."""

from __future__ import annotations

import json
import re
from typing import Any

from lineagehub.models import LineageResult, RunImpactAnalysis


def dumps_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def graph_cycles_payload(cycles: list[list[str]]) -> dict[str, Any]:
    return {
        "query_type": "graph_cycles",
        "cycle_count": len(cycles),
        "cycles": cycles,
    }


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


def dataset_catalog_row(
    *,
    name: str,
    dataset_type: str | None,
    uri: str | None,
    owner: str | None = None,
    description: str | None = None,
    tags: tuple[str, ...] | None = None,
    criticality: str | None = None,
    system: str | None = None,
) -> dict[str, Any]:
    """Shape for one dataset in catalog list/show JSON (nulls for missing optional fields)."""
    return {
        "name": name,
        "type": dataset_type,
        "uri": uri,
        "owner": owner,
        "description": description,
        "tags": list(tags) if tags is not None else None,
        "criticality": criticality,
        "system": system,
    }


def job_show_payload(
    *,
    name: str,
    description: str | None,
    inputs: list[str],
    outputs: list[str],
    latest_run: dict[str, str] | None,
    run_count: int,
) -> dict[str, Any]:
    return {
        "query_type": "job_show",
        "job": {"name": name, "description": description},
        "inputs": inputs,
        "outputs": outputs,
        "latest_run": latest_run,
        "run_count": run_count,
    }


def dataset_show_payload(
    *,
    name: str,
    dataset_type: str | None,
    uri: str | None,
    producer_jobs: list[str],
    consumer_jobs: list[str],
    upstream: list[LineageResult],
    downstream: list[LineageResult],
    owner: str | None = None,
    description: str | None = None,
    tags: tuple[str, ...] | None = None,
    criticality: str | None = None,
    system: str | None = None,
) -> dict[str, Any]:
    return {
        "query_type": "dataset_show",
        "dataset": dataset_catalog_row(
            name=name,
            dataset_type=dataset_type,
            uri=uri,
            owner=owner,
            description=description,
            tags=tags,
            criticality=criticality,
            system=system,
        ),
        "producer_jobs": producer_jobs,
        "consumer_jobs": consumer_jobs,
        "upstream": [{"name": x.name, "distance": x.distance} for x in upstream],
        "downstream": [{"name": x.name, "distance": x.distance} for x in downstream],
    }


def run_impact_payload(analysis: RunImpactAnalysis) -> dict[str, Any]:
    return {
        "query_type": "run_impact",
        "run_id": analysis.external_run_id,
        "job": analysis.job_name,
        "status": analysis.status,
        "error_message": analysis.error_message,
        "affected_count": len(analysis.affected),
        "output_datasets": list(analysis.output_datasets),
        "affected_datasets": [
            {
                "name": r.name,
                "distance": r.distance,
                "source_output": r.source_output,
            }
            for r in analysis.affected
        ],
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
