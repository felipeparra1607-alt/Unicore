from __future__ import annotations

from src.handoff import (
    HandoffRequest,
)

from src.jobs import (
    Job,
    create_job_from_handoff,
    get_job,
    job_to_dict,
    list_jobs,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
)

from src.runtime_context import (
    RuntimeContext,
)


class JobManager:
    """
    Fachada simple para manejar Jobs de UniCore.

    No ejecuta modelos por sí misma.

    Se encarga de:
    - crear Jobs;
    - persistir el RuntimeContext de origen;
    - leerlos;
    - listar;
    - gestionar transiciones;
    - mantener una API central para el Worker.
    """

    def create_from_handoff(
        self,
        handoff: HandoffRequest,
        runtime_context: RuntimeContext | None = None,
    ) -> Job:
        return create_job_from_handoff(
            handoff,
            runtime_context=runtime_context,
        )

    def get(
        self,
        job_id: str,
    ) -> Job | None:
        return get_job(
            job_id
        )

    def get_dict(
        self,
        job_id: str,
    ) -> dict | None:
        job = self.get(
            job_id
        )

        if job is None:
            return None

        return job_to_dict(
            job
        )

    def list(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Job]:
        return list_jobs(
            status=status,
            limit=limit,
        )

    def start(
        self,
        job_id: str,
    ) -> Job:
        return mark_job_running(
            job_id
        )

    def complete(
        self,
        job_id: str,
        result,
    ) -> Job:
        return mark_job_completed(
            job_id,
            result,
        )

    def fail(
        self,
        job_id: str,
        error,
    ) -> Job:
        return mark_job_failed(
            job_id,
            error,
        )