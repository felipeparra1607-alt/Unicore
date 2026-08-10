from __future__ import annotations

from src.job_manager import JobManager
from src.jobs import job_to_dict


def get_jobs_resource_payload(
    *,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    manager = JobManager()

    jobs = manager.list(
        status=status,
        limit=limit,
    )

    return {
        "count": len(jobs),
        "jobs": [
            job_to_dict(job)
            for job in jobs
        ],
    }


def get_job_resource_payload(
    job_id: str,
) -> dict:
    manager = JobManager()

    job = manager.get(
        job_id
    )

    if job is None:
        return {
            "ok": False,
            "error": "Job inexistente",
            "job_id": job_id,
        }

    return {
        "ok": True,
        "job": job_to_dict(job),
    }


def get_job_status_payload(
    job_id: str,
) -> dict:
    manager = JobManager()

    job = manager.get(
        job_id
    )

    if job is None:
        return {
            "ok": False,
            "error": "Job inexistente",
            "job_id": job_id,
        }

    return {
        "ok": True,
        "job_id": job.job_id,
        "status": job.status,
        "kind": job.kind,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error": job.error,
    }