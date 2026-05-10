"""Load lineage metadata from JSON files into the SQLite store."""

from __future__ import annotations

import json
import sqlite3
from itertools import product
from pathlib import Path
from typing import Any

from lineagehub.models import Dataset, Job, LineageEdge, Run
from lineagehub.store import MetadataStore

_ALLOWED_CRITICALITY = frozenset({"low", "medium", "high", "critical"})


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
        owner = _optional_string(item, "owner", f"dataset {name!r}")
        tags = _parse_dataset_tags(item, name)
        criticality = _parse_criticality(item, name)
        catalog_system = _optional_string(item, "system", f"dataset {name!r}")
        store.upsert_dataset(
            Dataset(
                name=name,
                dataset_type=item.get("type") if isinstance(item.get("type"), str) else None,
                uri=item.get("uri") if isinstance(item.get("uri"), str) else None,
                description=item.get("description") if isinstance(item.get("description"), str) else None,
                owner=owner,
                tags=tags,
                criticality=criticality,
                system=catalog_system,
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


def load_runs_json(store: MetadataStore, path: str | Path) -> None:
    """Load pipeline run rows from JSON (``runs`` array). Each entry needs ``run_id`` (external id string), ``job_name``, and ``status``."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    _expect_dict(data, "root")
    runs = data.get("runs")
    if not isinstance(runs, list):
        raise ValueError("'runs' must be a list")
    store.init_schema()

    for item in runs:
        _expect_dict(item, "run entry")
        external_id = item.get("run_id")
        job_name = item.get("job_name")
        status = item.get("status")
        if not external_id or not isinstance(external_id, str):
            raise ValueError("each run requires a non-empty string 'run_id'")
        if not job_name or not isinstance(job_name, str):
            raise ValueError(f"run {external_id!r} requires string 'job_name'")
        if not status or not isinstance(status, str):
            raise ValueError(f"run {external_id!r} requires string 'status'")

        job = store.get_job_by_name(job_name)
        if job is None or job.job_id is None:
            raise ValueError(f"run {external_id!r}: unknown job {job_name!r}")

        run = Run(
            job_id=job.job_id,
            status=status,
            external_run_id=external_id,
            started_at=item.get("started_at") if isinstance(item.get("started_at"), str) else None,
            ended_at=item.get("ended_at") if isinstance(item.get("ended_at"), str) else None,
            error_message=(
                item.get("error_message") if isinstance(item.get("error_message"), str) else None
            ),
        )
        try:
            store.insert_run(run)
        except sqlite3.IntegrityError as e:
            raise ValueError(
                f"run {external_id!r}: could not insert (duplicate run_id or invalid data)"
            ) from e


def _expect_dict(obj: Any, label: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be a JSON object")
    return obj


def _optional_string(item: dict[str, Any], key: str, label: str) -> str | None:
    raw = item.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{label}: '{key}' must be a string")
    return raw


def _parse_dataset_tags(item: dict[str, Any], dataset_name: str) -> tuple[str, ...] | None:
    raw = item.get("tags")
    if raw is None:
        return None
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError(f"dataset {dataset_name!r}: 'tags' must be a list of strings")
    return tuple(raw)


def _parse_criticality(item: dict[str, Any], dataset_name: str) -> str | None:
    raw = item.get("criticality")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"dataset {dataset_name!r}: 'criticality' must be a string")
    value = raw.strip().lower()
    if value not in _ALLOWED_CRITICALITY:
        raise ValueError(
            f"dataset {dataset_name!r}: invalid criticality {raw!r}; "
            f"expected one of {sorted(_ALLOWED_CRITICALITY)}"
        )
    return value
