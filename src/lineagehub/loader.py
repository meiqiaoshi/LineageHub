"""Load lineage metadata from JSON files into the SQLite store."""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Any

from lineagehub.models import Dataset, Job, LineageEdge
from lineagehub.store import MetadataStore


def load_lineage_json(store: MetadataStore, path: str | Path) -> None:
    """Parse a lineage JSON file and persist datasets, jobs, and lineage edges.

    Expected shape matches ``examples/sample_lineage.json``: top-level ``datasets``
    and ``jobs`` arrays. For each job, an edge is created from every input dataset
    to every output dataset (job attribution stored on the edge).
    """
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    _expect_dict(data, "root")
    store.init_schema()

    datasets = data.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("'datasets' must be a list")
    for item in datasets:
        _expect_dict(item, "dataset entry")
        name = item.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("each dataset requires a non-empty string 'name'")
        store.upsert_dataset(
            Dataset(
                name=name,
                dataset_type=item.get("type") if isinstance(item.get("type"), str) else None,
                uri=item.get("uri") if isinstance(item.get("uri"), str) else None,
                description=item.get("description") if isinstance(item.get("description"), str) else None,
            )
        )

    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("'jobs' must be a list")
    for item in jobs:
        _expect_dict(item, "job entry")
        job_name = item.get("name")
        if not job_name or not isinstance(job_name, str):
            raise ValueError("each job requires a non-empty string 'name'")
        inputs = item.get("inputs")
        outputs = item.get("outputs")
        if not isinstance(inputs, list) or not all(isinstance(x, str) for x in inputs):
            raise ValueError(f"job {job_name!r} requires 'inputs' as a list of strings")
        if not isinstance(outputs, list) or not all(isinstance(x, str) for x in outputs):
            raise ValueError(f"job {job_name!r} requires 'outputs' as a list of strings")
        if not inputs or not outputs:
            raise ValueError(f"job {job_name!r} must have non-empty 'inputs' and 'outputs'")

        job_id = store.upsert_job(
            Job(
                name=job_name,
                system=item.get("system") if isinstance(item.get("system"), str) else None,
                description=item.get("description") if isinstance(item.get("description"), str) else None,
            )
        )

        for upstream_name, downstream_name in product(inputs, outputs):
            up_id = store.get_dataset_id_by_name(upstream_name)
            if up_id is None:
                raise ValueError(
                    f"job {job_name!r}: unknown upstream dataset {upstream_name!r}"
                )
            down_id = store.get_dataset_id_by_name(downstream_name)
            if down_id is None:
                raise ValueError(
                    f"job {job_name!r}: unknown downstream dataset {downstream_name!r}"
                )
            store.insert_lineage_edge(
                LineageEdge(
                    upstream_dataset_id=up_id,
                    downstream_dataset_id=down_id,
                    job_id=job_id,
                )
            )


def _expect_dict(obj: Any, label: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be a JSON object")
    return obj
