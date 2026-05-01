"""SQLite persistence for lineage metadata (see docs/metadata_model.md)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lineagehub.models import Dataset, Job, LineageEdge, Run


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT,
    uri TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    system TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    error_message TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS lineage_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    upstream_dataset_id INTEGER NOT NULL,
    downstream_dataset_id INTEGER NOT NULL,
    job_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (upstream_dataset_id) REFERENCES datasets(dataset_id),
    FOREIGN KEY (downstream_dataset_id) REFERENCES datasets(dataset_id),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    UNIQUE (upstream_dataset_id, downstream_dataset_id, job_id)
);
"""


class MetadataStore:
    """Local SQLite metadata store."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def upsert_dataset(self, dataset: Dataset) -> int:
        """Insert or update by name; returns dataset_id."""
        now = utc_now_iso()
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT dataset_id, created_at FROM datasets WHERE name = ?",
                (dataset.name,),
            ).fetchone()
            if row:
                dataset_id = int(row["dataset_id"])
                conn.execute(
                    """UPDATE datasets SET type = ?, uri = ?, description = ?, updated_at = ?
                       WHERE dataset_id = ?""",
                    (dataset.dataset_type, dataset.uri, dataset.description, now, dataset_id),
                )
                conn.commit()
                return dataset_id
            created = dataset.created_at or now
            updated = dataset.updated_at or now
            cur = conn.execute(
                """INSERT INTO datasets (name, type, uri, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    dataset.name,
                    dataset.dataset_type,
                    dataset.uri,
                    dataset.description,
                    created,
                    updated,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def upsert_job(self, job: Job) -> int:
        """Insert or update by name; returns job_id."""
        now = utc_now_iso()
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT job_id, created_at FROM jobs WHERE name = ?",
                (job.name,),
            ).fetchone()
            if row:
                job_id = int(row["job_id"])
                conn.execute(
                    """UPDATE jobs SET system = ?, description = ?, updated_at = ?
                       WHERE job_id = ?""",
                    (job.system, job.description, now, job_id),
                )
                conn.commit()
                return job_id
            created = job.created_at or now
            updated = job.updated_at or now
            cur = conn.execute(
                """INSERT INTO jobs (name, system, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job.name, job.system, job.description, created, updated),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def insert_run(self, run: Run) -> int:
        """Insert a run; returns run_id."""
        conn = self.connect()
        try:
            cur = conn.execute(
                """INSERT INTO runs (job_id, status, started_at, ended_at, error_message)
                   VALUES (?, ?, ?, ?, ?)""",
                (run.job_id, run.status, run.started_at, run.ended_at, run.error_message),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def insert_lineage_edge(self, edge: LineageEdge) -> int:
        """Insert an edge if missing (unique on upstream, downstream, job_id); returns edge_id."""
        now = utc_now_iso()
        created_at = edge.created_at or now
        conn = self.connect()
        try:
            if edge.job_id is None:
                row = conn.execute(
                    """SELECT edge_id FROM lineage_edges
                       WHERE upstream_dataset_id = ?
                         AND downstream_dataset_id = ?
                         AND job_id IS NULL""",
                    (edge.upstream_dataset_id, edge.downstream_dataset_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT edge_id FROM lineage_edges
                       WHERE upstream_dataset_id = ?
                         AND downstream_dataset_id = ?
                         AND job_id = ?""",
                    (edge.upstream_dataset_id, edge.downstream_dataset_id, edge.job_id),
                ).fetchone()
            if row:
                return int(row["edge_id"])
            cur = conn.execute(
                """INSERT INTO lineage_edges
                   (upstream_dataset_id, downstream_dataset_id, job_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    edge.upstream_dataset_id,
                    edge.downstream_dataset_id,
                    edge.job_id,
                    created_at,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_dataset_by_name(self, name: str) -> Dataset | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM datasets WHERE name = ?", (name,)).fetchone()
            return None if row is None else _row_to_dataset(row)
        finally:
            conn.close()

    def get_dataset_id_by_name(self, name: str) -> int | None:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT dataset_id FROM datasets WHERE name = ?", (name,)
            ).fetchone()
            return None if row is None else int(row["dataset_id"])
        finally:
            conn.close()

    def get_job_by_name(self, name: str) -> Job | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE name = ?", (name,)).fetchone()
            return None if row is None else _row_to_job(row)
        finally:
            conn.close()

    def list_datasets(self) -> list[Dataset]:
        conn = self.connect()
        try:
            rows = conn.execute("SELECT * FROM datasets ORDER BY name").fetchall()
            return [_row_to_dataset(r) for r in rows]
        finally:
            conn.close()

    def list_lineage_edges(self) -> list[LineageEdge]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT edge_id, upstream_dataset_id, downstream_dataset_id, job_id, created_at "
                "FROM lineage_edges"
            ).fetchall()
            return [_row_to_edge(r) for r in rows]
        finally:
            conn.close()


def _row_to_dataset(row: sqlite3.Row) -> Dataset:
    return Dataset(
        dataset_id=int(row["dataset_id"]),
        name=str(row["name"]),
        dataset_type=row["type"],
        uri=row["uri"],
        description=row["description"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        job_id=int(row["job_id"]),
        name=str(row["name"]),
        system=row["system"],
        description=row["description"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_edge(row: sqlite3.Row) -> LineageEdge:
    return LineageEdge(
        edge_id=int(row["edge_id"]),
        upstream_dataset_id=int(row["upstream_dataset_id"]),
        downstream_dataset_id=int(row["downstream_dataset_id"]),
        job_id=row["job_id"],
        created_at=row["created_at"],
    )
