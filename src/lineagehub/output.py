"""Structured JSON payloads for CLI (and future API reuse)."""

from __future__ import annotations

import json
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
