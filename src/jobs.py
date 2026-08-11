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
from src.runtime_context import (
    RuntimeContext,
    build_runtime_context,
)


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

    # Contexto de ejecución persistido.
    conversation_id: str
    study_session_id: int | None
    allow_writes: bool
    allowed_paths: tuple[str, ...]

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


def _parse_json_list(
    raw_value: Any,
) -> list[str]:
    raw_text = str(
        raw_value
        or "[]"
    )

    try:
        parsed = json.loads(
            raw_text
        )
    except json.JSONDecodeError:
        parsed = []

    if not isinstance(
        parsed,
        list,
    ):
        parsed = []

    return [
        str(value)
        for value in parsed
        if str(value).strip()
    ]


def _legacy_conversation_id(
    job_id: str,
) -> str:
    clean_job_id = str(
        job_id
        or "legacy"
    ).strip()

    suffix = (
        clean_job_id[4:]
        if clean_job_id.startswith("job_")
        else clean_job_id
    )

    return (
        "conv_legacy_"
        + suffix
    )


def row_to_job(
    row: sqlite3.Row,
) -> Job:
    source_uris = _parse_json_list(
        row["source_uris"]
    )

    allowed_paths = _parse_json_list(
        row["allowed_paths"]
    )

    conversation_id = str(
        row["conversation_id"]
        or ""
    ).strip()

    if not conversation_id:
        conversation_id = (
            _legacy_conversation_id(
                row["job_id"]
            )
        )

    study_session_raw = (
        row["study_session_id"]
    )

    study_session_id = (
        int(study_session_raw)
        if study_session_raw is not None
        else None
    )

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
            source_uris
        ),
        requires_write=bool(
            row[
                "requires_write"
            ]
        ),
        conversation_id=(
            conversation_id
        ),
        study_session_id=(
            study_session_id
        ),
        allow_writes=bool(
            row[
                "allow_writes"
            ]
        ),
        allowed_paths=tuple(
            allowed_paths
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

    result[
        "allowed_paths"
    ] = list(
        job.allowed_paths
    )

    return result


def runtime_context_from_job(
    job: Job,
) -> RuntimeContext:
    """
    Reconstruye el RuntimeContext asociado a un Job.

    El job_id se incorpora aquí porque el contexto persistido
    pertenece ya a una ejecución concreta del Worker.
    """

    return build_runtime_context(
        conversation_id=(
            job.conversation_id
        ),
        job_id=(
            job.job_id
        ),
        study_session_id=(
            job.study_session_id
        ),
        allow_writes=(
            job.allow_writes
        ),
        allowed_paths=(
            job.allowed_paths
        ),
    )


# ============================================================
# MIGRACIÓN
# ============================================================


def _existing_job_columns(
    connection: sqlite3.Connection,
) -> set[str]:
    rows = connection.execute(
        "PRAGMA table_info(jobs)"
    ).fetchall()

    return {
        str(row["name"])
        for row in rows
    }


def ensure_jobs_table(
) -> None:
    """
    Crea la tabla y migra instalaciones antiguas de Jobs sin
    borrar ningún Job existente.
    """

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
                conversation_id TEXT,
                study_session_id INTEGER,
                allow_writes INTEGER NOT NULL DEFAULT 0,
                allowed_paths TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT
            )
            """
        )

        columns = _existing_job_columns(
            connection
        )

        migrations = {
            "conversation_id": (
                "ALTER TABLE jobs "
                "ADD COLUMN conversation_id TEXT"
            ),
            "study_session_id": (
                "ALTER TABLE jobs "
                "ADD COLUMN study_session_id INTEGER"
            ),
            "allow_writes": (
                "ALTER TABLE jobs "
                "ADD COLUMN allow_writes INTEGER "
                "NOT NULL DEFAULT 0"
            ),
            "allowed_paths": (
                "ALTER TABLE jobs "
                "ADD COLUMN allowed_paths TEXT "
                "NOT NULL DEFAULT '[]'"
            ),
        }

        for column_name, sql in (
            migrations.items()
        ):
            if column_name not in columns:
                connection.execute(
                    sql
                )

        # Los Jobs creados antes de RuntimeContext reciben un
        # conversation_id estable derivado de su job_id.
        connection.execute(
            """
            UPDATE jobs
            SET conversation_id =
                'conv_legacy_' ||
                CASE
                    WHEN job_id LIKE 'job_%'
                    THEN substr(job_id, 5)
                    ELSE job_id
                END
            WHERE conversation_id IS NULL
               OR trim(conversation_id) = ''
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

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_jobs_conversation_id
            ON jobs(conversation_id)
            """
        )

        connection.commit()


# ============================================================
# CREATE
# ============================================================


def create_job_from_handoff(
    handoff: HandoffRequest,
    runtime_context: RuntimeContext | None = None,
) -> Job:
    ensure_jobs_table()

    if runtime_context is None:
        runtime_context = (
            build_runtime_context()
        )

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

    allowed_paths_json = (
        json.dumps(
            list(
                runtime_context.allowed_paths
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
                conversation_id,
                study_session_id,
                allow_writes,
                allowed_paths,
                created_at,
                started_at,
                completed_at,
                result,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                runtime_context.conversation_id,
                runtime_context.study_session_id,
                1
                if runtime_context.allow_writes
                else 0,
                allowed_paths_json,
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