"""SQLite persistence for lineage metadata (see docs/metadata_model.md)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dataclasses import dataclass

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
    external_run_id TEXT,
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


@dataclass(frozen=True)
class RunContext:
    """Resolved run plus job name for operational queries."""

    external_run_id: str
    internal_run_id: int
    job_id: int
    job_name: str
    status: str
    started_at: str | None
    ended_at: str | None
    error_message: str | None


@dataclass(frozen=True)
class RunRecord:
    """One run row joined with job name for listings."""

    internal_run_id: int
    external_run_id: str | None
    job_id: int
    job_name: str
    status: str
    started_at: str | None
    ended_at: str | None
    error_message: str | None


def _apply_runs_migrations(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "external_run_id" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN external_run_id TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_external_run_id "
        "ON runs(external_run_id) WHERE external_run_id IS NOT NULL"
    )


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
            _apply_runs_migrations(conn)
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
        """Insert a run; returns internal numeric ``run_id``."""
        conn = self.connect()
        try:
            _apply_runs_migrations(conn)
            cur = conn.execute(
                """INSERT INTO runs (job_id, status, started_at, ended_at, error_message, external_run_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run.job_id,
                    run.status,
                    run.started_at,
                    run.ended_at,
                    run.error_message,
                    run.external_run_id,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_run_by_external_id(self, external_run_id: str) -> Run | None:
        conn = self.connect()
        try:
            _apply_runs_migrations(conn)
            row = conn.execute(
                "SELECT * FROM runs WHERE external_run_id = ?", (external_run_id,)
            ).fetchone()
            return None if row is None else _row_to_run(row)
        finally:
            conn.close()

    def fetch_run_context_by_external_id(self, external_run_id: str) -> RunContext | None:
        conn = self.connect()
        try:
            _apply_runs_migrations(conn)
            row = conn.execute(
                """SELECT runs.*, jobs.name AS job_name FROM runs
                   INNER JOIN jobs ON runs.job_id = jobs.job_id
                   WHERE runs.external_run_id = ?""",
                (external_run_id,),
            ).fetchone()
            return None if row is None else _row_to_run_context(row)
        finally:
            conn.close()

    def list_runs(
        self,
        *,
        status: str | None = None,
        job_name: str | None = None,
        since: str | None = None,
        limit: int | None = None,
    ) -> list[RunRecord]:
        """
        List runs ordered by most recent first.

        Filters:
        - status: match runs.status
        - job_name: match jobs.name
        - since: include runs with started_at >= since (ISO-8601 string)
        - limit: max number of rows returned
        """
        conn = self.connect()
        try:
            _apply_runs_migrations(conn)
            clauses: list[str] = []
            params: list[object] = []

            if status is not None:
                clauses.append("runs.status = ?")
                params.append(status)

            if job_name is not None:
                clauses.append("jobs.name = ?")
                params.append(job_name)

            if since is not None:
                clauses.append("runs.started_at IS NOT NULL AND runs.started_at >= ?")
                params.append(since)

            where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            limit_sql = " LIMIT ?" if limit is not None else ""
            if limit is not None:
                params.append(int(limit))

            rows = conn.execute(
                "SELECT runs.run_id, runs.external_run_id, runs.job_id, jobs.name AS job_name, "
                "runs.status, runs.started_at, runs.ended_at, runs.error_message "
                "FROM runs INNER JOIN jobs ON runs.job_id = jobs.job_id"
                + where_sql
                + " ORDER BY (runs.started_at IS NULL) ASC, runs.started_at DESC, runs.run_id DESC"
                + limit_sql,
                tuple(params),
            ).fetchall()
            return [_row_to_run_record(r) for r in rows]
        finally:
            conn.close()

    def list_output_dataset_ids_for_job(self, job_id: int) -> list[int]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT downstream_dataset_id FROM lineage_edges WHERE job_id = ?",
                (job_id,),
            ).fetchall()
            return [int(r["downstream_dataset_id"]) for r in rows]
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


def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(
        run_id=int(row["run_id"]),
        job_id=int(row["job_id"]),
        status=str(row["status"]),
        external_run_id=row["external_run_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        error_message=row["error_message"],
    )


def _row_to_run_context(row: sqlite3.Row) -> RunContext:
    return RunContext(
        external_run_id=str(row["external_run_id"]),
        internal_run_id=int(row["run_id"]),
        job_id=int(row["job_id"]),
        job_name=str(row["job_name"]),
        status=str(row["status"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        error_message=row["error_message"],
    )


def _row_to_run_record(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        internal_run_id=int(row["run_id"]),
        external_run_id=row["external_run_id"],
        job_id=int(row["job_id"]),
        job_name=str(row["job_name"]),
        status=str(row["status"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        error_message=row["error_message"],
    )


def _row_to_edge(row: sqlite3.Row) -> LineageEdge:
    return LineageEdge(
        edge_id=int(row["edge_id"]),
        upstream_dataset_id=int(row["upstream_dataset_id"]),
        downstream_dataset_id=int(row["downstream_dataset_id"]),
        job_id=row["job_id"],
        created_at=row["created_at"],
    )
