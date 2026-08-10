from __future__ import annotations

import json

from src.handoff import (
    build_handoff_request,
)

from src.job_manager import (
    JobManager,
)

from src.job_worker import (
    JobWorker,
)


def run_job_evals(
) -> dict:
    manager = (
        JobManager()
    )

    checks = []

    # ========================================================
    # READ-ONLY JOB
    # ========================================================

    read_handoff = (
        build_handoff_request(
            kind="artifact",
            objective=(
                "Crear artefacto de prueba"
            ),
            context_summary=(
                "Eval local del lifecycle"
            ),
            expected_output=(
                "Resultado de prueba"
            ),
            requires_write=False,
        )
    )

    read_job = (
        manager.create_from_handoff(
            read_handoff
        )
    )

    checks.append({
        "name": "created_pending",
        "passed": (
            read_job.status
            == "pending"
        ),
    })

    read_result = (
        JobWorker(
            allow_writes=False
        ).run(
            read_job.job_id
        )
    )

    read_completed_job = (
        manager.get(
            read_job.job_id
        )
    )

    checks.append({
        "name": (
            "readonly_job_completed"
        ),
        "passed": (
            read_result.get("ok")
            is True
            and read_completed_job
            is not None
            and read_completed_job.status
            == "completed"
        ),
    })

    # ========================================================
    # WRITE JOB BLOQUEADO
    # ========================================================

    write_handoff = (
        build_handoff_request(
            kind="long_analysis",
            objective=(
                "Modificar algo de prueba"
            ),
            context_summary=(
                "Eval de permisos"
            ),
            expected_output=(
                "Resultado de prueba"
            ),
            requires_write=True,
        )
    )

    write_job = (
        manager.create_from_handoff(
            write_handoff
        )
    )

    write_result = (
        JobWorker(
            allow_writes=False
        ).run(
            write_job.job_id
        )
    )

    blocked_job = (
        manager.get(
            write_job.job_id
        )
    )

    checks.append({
        "name": (
            "write_job_blocked"
        ),
        "passed": (
            write_result.get("ok")
            is False
            and blocked_job
            is not None
            and blocked_job.status
            == "failed"
        ),
    })

    failed = [
        check
        for check in checks
        if not check[
            "passed"
        ]
    ]

    return {
        "ok": (
            len(failed)
            == 0
        ),
        "passed_count": (
            len(checks)
            - len(failed)
        ),
        "failed_count": (
            len(failed)
        ),
        "checks": checks,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            run_job_evals(),
            ensure_ascii=False,
            indent=2,
        )
    )