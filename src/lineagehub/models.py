"""Metadata entities aligned with docs/metadata_model.md and the MVP SQLite schema."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Dataset:
    """A data asset (table, mart, dashboard, etc.)."""

    name: str
    dataset_id: int | None = None
    dataset_type: str | None = None
    uri: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Job:
    """A process that reads input datasets and produces outputs (edges stored separately)."""

    name: str
    job_id: int | None = None
    system: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Run:
    """One execution of a job."""

    job_id: int
    status: str
    run_id: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    error_message: str | None = None


@dataclass
class LineageEdge:
    """Directed dependency: upstream_dataset -> downstream_dataset."""

    upstream_dataset_id: int
    downstream_dataset_id: int
    edge_id: int | None = None
    job_id: int | None = None
    created_at: str | None = None
