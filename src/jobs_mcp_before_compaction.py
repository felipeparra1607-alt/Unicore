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
# COMPACTACIÓN
# ============================================================


def job_summary(
    job: Job,
) -> dict:
    """
    Representación compacta para listados.

    No incluye:
    - context_summary completo;
    - result completo.

    Así evitamos introducir artefactos largos
    en el contexto del agente solo por listar Jobs.
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
            job.objective
        ),
        "expected_output": (
            job.expected_output
        ),
        "requires_write": (
            job.requires_write
        ),
        "created_at": (
            job.created_at
        ),
        "started_at": (
            job.started_at
        ),
        "completed_at": (
            job.completed_at
        ),
        "has_result": (
            has_result
        ),
        "error": (
            job.error
        ),
    }


# ============================================================
# PAYLOADS
# ============================================================


def get_jobs_resource_payload(
    *,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    manager = (
        JobManager()
    )

    jobs = manager.list(
        status=status,
        limit=limit,
    )

    return {
        "ok": True,
        "count": len(
            jobs
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
    Expone Jobs mediante MCP.

    Tools:
    - get_job_status
    - list_jobs

    Resources:
    - unicore://jobs
    - unicore://jobs/{job_id}
    """

    # --------------------------------------------------------
    # TOOLS
    # --------------------------------------------------------

    @mcp.tool()
    def get_job_status(
        job_id: str,
    ) -> dict:
        """
        Consulta el estado compacto de un Job de UniCore.

        No devuelve el resultado largo del Job.
        Para recuperar el Job completo utiliza
        unicore://jobs/{job_id}.
        """

        return get_job_status_payload(
            job_id
        )


    @mcp.tool()
    def list_jobs(
        status: str | None = None,
        limit: int = 20,
    ) -> dict:
        """
        Lista Jobs de UniCore de forma compacta.

        status puede ser:
        pending, running, completed o failed.
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
    # DIRECT RESOURCE
    # --------------------------------------------------------

    @mcp.resource(
        "unicore://jobs"
    )
    def jobs_resource(
    ) -> str:
        """
        Lista compacta de los Jobs más recientes.
        """

        return _json(
            get_jobs_resource_payload(
                limit=20
            )
        )


    # --------------------------------------------------------
    # RESOURCE TEMPLATE
    # --------------------------------------------------------

    @mcp.resource(
        "unicore://jobs/{job_id}"
    )
    def job_resource(
        job_id: str,
    ) -> str:
        """
        Devuelve un Job concreto, incluido su resultado
        persistido cuando haya terminado.
        """

        return _json(
            get_job_resource_payload(
                job_id
            )
        )
