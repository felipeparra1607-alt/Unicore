from __future__ import annotations

import json
import sqlite3
import uuid

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.handoff import HandoffRequest


# ============================================================
# RUTAS
# ============================================================


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "unicore.db"
)


# ============================================================
# ESTADOS
# ============================================================


JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"


SUPPORTED_JOB_STATUSES = {
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
}


# ============================================================
# MODELO
# ============================================================


@dataclass(frozen=True)
class Job:
    job_id: str

    status: str

    kind: str

    objective: str

    context_summary: str

    expected_output: str

    source_uris: tuple[str, ...]

    requires_write: bool

    created_at: str

    started_at: str | None

    completed_at: str | None

    result: str | None

    error: str | None


# ============================================================
# UTILIDADES
# ============================================================


def utc_now_iso() -> str:
    return (
        datetime.utcnow()
        .isoformat(
            timespec="seconds"
        )
        + "Z"
    )


def get_connection(
) -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


def row_to_job(
    row: sqlite3.Row,
) -> Job:
    source_uris_raw = (
        row["source_uris"]
        or "[]"
    )

    try:
        parsed_source_uris = (
            json.loads(
                source_uris_raw
            )
        )

    except json.JSONDecodeError:
        parsed_source_uris = []

    if not isinstance(
        parsed_source_uris,
        list,
    ):
        parsed_source_uris = []

    return Job(
        job_id=(
            row["job_id"]
        ),
        status=(
            row["status"]
        ),
        kind=(
            row["kind"]
        ),
        objective=(
            row["objective"]
        ),
        context_summary=(
            row[
                "context_summary"
            ]
        ),
        expected_output=(
            row[
                "expected_output"
            ]
        ),
        source_uris=tuple(
            str(uri)
            for uri in parsed_source_uris
        ),
        requires_write=bool(
            row[
                "requires_write"
            ]
        ),
        created_at=(
            row[
                "created_at"
            ]
        ),
        started_at=(
            row[
                "started_at"
            ]
        ),
        completed_at=(
            row[
                "completed_at"
            ]
        ),
        result=(
            row[
                "result"
            ]
        ),
        error=(
            row[
                "error"
            ]
        ),
    )


def job_to_dict(
    job: Job,
) -> dict:
    result = asdict(
        job
    )

    result[
        "source_uris"
    ] = list(
        job.source_uris
    )

    return result


# ============================================================
# MIGRACIÓN
# ============================================================


def ensure_jobs_table(
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                kind TEXT NOT NULL,
                objective TEXT NOT NULL,
                context_summary TEXT NOT NULL,
                expected_output TEXT NOT NULL,
                source_uris TEXT NOT NULL,
                requires_write INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_jobs_status
            ON jobs(status)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_jobs_created_at
            ON jobs(created_at)
            """
        )

        connection.commit()


# ============================================================
# CREATE
# ============================================================


def create_job_from_handoff(
    handoff: HandoffRequest,
) -> Job:
    ensure_jobs_table()

    job_id = (
        "job_"
        + uuid.uuid4().hex
    )

    created_at = (
        utc_now_iso()
    )

    source_uris_json = (
        json.dumps(
            list(
                handoff.source_uris
            ),
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )
    )

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                job_id,
                status,
                kind,
                objective,
                context_summary,
                expected_output,
                source_uris,
                requires_write,
                created_at,
                started_at,
                completed_at,
                result,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                JOB_STATUS_PENDING,
                handoff.kind,
                handoff.objective,
                handoff.context_summary,
                handoff.expected_output,
                source_uris_json,
                1
                if handoff.requires_write
                else 0,
                created_at,
                None,
                None,
                None,
                None,
            ),
        )

        connection.commit()

    job = get_job(
        job_id
    )

    if job is None:
        raise RuntimeError(
            "El Job se creó pero no pudo recuperarse"
        )

    return job


# ============================================================
# READ
# ============================================================


def get_job(
    job_id: str,
) -> Job | None:
    ensure_jobs_table()

    clean_job_id = str(
        job_id
        or ""
    ).strip()

    if not clean_job_id:
        return None

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE job_id = ?
            """,
            (
                clean_job_id,
            ),
        ).fetchone()

    if row is None:
        return None

    return row_to_job(
        row
    )


def list_jobs(
    status: str | None = None,
    limit: int = 50,
) -> list[Job]:
    ensure_jobs_table()

    clean_limit = max(
        1,
        min(
            int(limit),
            200,
        ),
    )

    with get_connection() as connection:
        if status is None:
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    clean_limit,
                ),
            ).fetchall()

        else:
            clean_status = str(
                status
            ).strip().casefold()

            if (
                clean_status
                not in SUPPORTED_JOB_STATUSES
            ):
                raise ValueError(
                    "Estado de Job no soportado: "
                    f"{clean_status}"
                )

            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    clean_status,
                    clean_limit,
                ),
            ).fetchall()

    return [
        row_to_job(
            row
        )
        for row in rows
    ]


# ============================================================
# TRANSICIONES
# ============================================================


def mark_job_running(
    job_id: str,
) -> Job:
    ensure_jobs_table()

    current_job = get_job(
        job_id
    )

    if current_job is None:
        raise ValueError(
            "Job inexistente"
        )

    if (
        current_job.status
        != JOB_STATUS_PENDING
    ):
        raise ValueError(
            "Solo un Job pending "
            "puede pasar a running"
        )

    started_at = (
        utc_now_iso()
    )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                started_at = ?,
                error = NULL
            WHERE job_id = ?
            """,
            (
                JOB_STATUS_RUNNING,
                started_at,
                job_id,
            ),
        )

        connection.commit()

    updated_job = get_job(
        job_id
    )

    if updated_job is None:
        raise RuntimeError(
            "No se pudo recuperar el Job actualizado"
        )

    return updated_job


def mark_job_completed(
    job_id: str,
    result: Any,
) -> Job:
    ensure_jobs_table()

    current_job = get_job(
        job_id
    )

    if current_job is None:
        raise ValueError(
            "Job inexistente"
        )

    if (
        current_job.status
        != JOB_STATUS_RUNNING
    ):
        raise ValueError(
            "Solo un Job running "
            "puede completarse"
        )

    completed_at = (
        utc_now_iso()
    )

    serialized_result = (
        result
        if isinstance(
            result,
            str,
        )
        else json.dumps(
            result,
            ensure_ascii=False,
            default=str,
        )
    )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                completed_at = ?,
                result = ?,
                error = NULL
            WHERE job_id = ?
            """,
            (
                JOB_STATUS_COMPLETED,
                completed_at,
                serialized_result,
                job_id,
            ),
        )

        connection.commit()

    updated_job = get_job(
        job_id
    )

    if updated_job is None:
        raise RuntimeError(
            "No se pudo recuperar el Job completado"
        )

    return updated_job


def mark_job_failed(
    job_id: str,
    error: Any,
) -> Job:
    ensure_jobs_table()

    current_job = get_job(
        job_id
    )

    if current_job is None:
        raise ValueError(
            "Job inexistente"
        )

    if (
        current_job.status
        not in {
            JOB_STATUS_PENDING,
            JOB_STATUS_RUNNING,
        }
    ):
        raise ValueError(
            "Solo un Job pending o running "
            "puede marcarse como failed"
        )

    completed_at = (
        utc_now_iso()
    )

    clean_error = str(
        error
        or "Error desconocido"
    ).strip()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                completed_at = ?,
                error = ?
            WHERE job_id = ?
            """,
            (
                JOB_STATUS_FAILED,
                completed_at,
                clean_error,
                job_id,
            ),
        )

        connection.commit()

    updated_job = get_job(
        job_id
    )

    if updated_job is None:
        raise RuntimeError(
            "No se pudo recuperar el Job fallido"
        )

    return updated_job