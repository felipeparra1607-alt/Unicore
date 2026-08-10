from __future__ import annotations

import json

from src.job_manager import (
    JobManager,
)

from src.jobs import (
    Job,
    job_to_dict,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================


DEFAULT_JOB_LIST_LIMIT = 5
MAXIMUM_JOB_LIST_LIMIT = 5


# ============================================================
# SERIALIZACIÓN
# ============================================================


def _json(
    value,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


# ============================================================
# UTILIDADES
# ============================================================


def compact_string(
    value,
    maximum_characters: int,
) -> str | None:
    if value is None:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    if (
        len(text)
        <= maximum_characters
    ):
        return text

    return (
        text[
            :maximum_characters
        ]
        + "..."
    )


def normalize_list_limit(
    limit: int,
) -> int:
    """
    Impone un límite duro.

    Incluso si el modelo solicita 20 o 100 Jobs,
    el catálogo conversacional devuelve como
    máximo 5.
    """

    try:
        clean_limit = int(
            limit
        )

    except (
        TypeError,
        ValueError,
    ):
        clean_limit = (
            DEFAULT_JOB_LIST_LIMIT
        )

    return max(
        1,
        min(
            clean_limit,
            MAXIMUM_JOB_LIST_LIMIT,
        ),
    )


# ============================================================
# RESUMEN COMPACTO
# ============================================================


def job_summary(
    job: Job,
) -> dict:
    """
    Representación mínima para listados.

    El resultado largo NO se incluye aquí.
    """

    has_result = bool(
        str(
            job.result
            or ""
        ).strip()
    )

    return {
        "job_id": (
            job.job_id
        ),
        "status": (
            job.status
        ),
        "kind": (
            job.kind
        ),
        "objective": (
            compact_string(
                job.objective,
                180,
            )
        ),
        "requires_write": (
            job.requires_write
        ),
        "created_at": (
            job.created_at
        ),
        "completed_at": (
            job.completed_at
        ),
        "has_result": (
            has_result
        ),
        "has_error": bool(
            str(
                job.error
                or ""
            ).strip()
        ),
    }


# ============================================================
# PAYLOADS
# ============================================================


def get_jobs_resource_payload(
    *,
    status: str | None = None,
    limit: int = DEFAULT_JOB_LIST_LIMIT,
) -> dict:
    manager = (
        JobManager()
    )

    clean_limit = (
        normalize_list_limit(
            limit
        )
    )

    jobs = manager.list(
        status=status,
        limit=clean_limit,
    )

    return {
        "ok": True,
        "count": len(
            jobs
        ),
        "limit": (
            clean_limit
        ),
        "jobs": [
            job_summary(
                job
            )
            for job in jobs
        ],
    }


def get_job_resource_payload(
    job_id: str,
) -> dict:
    """
    Job completo.

    Este endpoint sí incluye result porque ya
    estamos consultando un Job concreto.
    """

    manager = (
        JobManager()
    )

    job = manager.get(
        job_id
    )

    if job is None:
        return {
            "ok": False,
            "error": (
                "Job inexistente"
            ),
            "job_id": (
                job_id
            ),
        }

    return {
        "ok": True,
        "job": (
            job_to_dict(
                job
            )
        ),
    }


def get_job_status_payload(
    job_id: str,
) -> dict:
    """
    Estado compacto de un Job.

    No incluye result.
    """

    manager = (
        JobManager()
    )

    job = manager.get(
        job_id
    )

    if job is None:
        return {
            "ok": False,
            "error": (
                "Job inexistente"
            ),
            "job_id": (
                job_id
            ),
        }

    return {
        "ok": True,
        "job": (
            job_summary(
                job
            )
        ),
    }


# ============================================================
# REGISTRO MCP
# ============================================================


def register_jobs_mcp(
    mcp,
) -> None:
    """
    Capacidades MCP de Jobs.

    Tools:
    - get_job_status
    - list_jobs

    Resources:
    - unicore://jobs
    - unicore://jobs/{job_id}
    """

    # --------------------------------------------------------
    # TOOL — STATUS
    # --------------------------------------------------------

    @mcp.tool()
    def get_job_status(
        job_id: str,
    ) -> dict:
        """
        Consulta el estado compacto de un Job.

        Para recuperar el resultado completo utiliza
        el Resource unicore://jobs/{job_id}.
        """

        return get_job_status_payload(
            job_id
        )


    # --------------------------------------------------------
    # TOOL — LIST
    # --------------------------------------------------------

    @mcp.tool()
    def list_jobs(
        status: str | None = None,
        limit: int = DEFAULT_JOB_LIST_LIMIT,
    ) -> dict:
        """
        Lista hasta 5 Jobs recientes de UniCore.

        Puede filtrarse por:
        pending, running, completed o failed.

        Para obtener un resultado largo consulta después
        el Resource específico del Job.
        """

        try:
            return (
                get_jobs_resource_payload(
                    status=status,
                    limit=limit,
                )
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    str(
                        error
                    )
                ),
            }


    # --------------------------------------------------------
    # RESOURCE — LIST
    # --------------------------------------------------------

    @mcp.resource(
        "unicore://jobs"
    )
    def jobs_resource(
    ) -> str:
        """
        Lista compacta de los cinco Jobs
        más recientes.
        """

        return _json(
            get_jobs_resource_payload(
                limit=(
                    DEFAULT_JOB_LIST_LIMIT
                )
            )
        )


    # --------------------------------------------------------
    # RESOURCE TEMPLATE — JOB COMPLETO
    # --------------------------------------------------------

    @mcp.resource(
        "unicore://jobs/{job_id}"
    )
    def job_resource(
        job_id: str,
    ) -> str:
        """
        Devuelve un Job concreto.

        Incluye el resultado persistido si el Job
        ya ha terminado.
        """

        return _json(
            get_job_resource_payload(
                job_id
            )
        )