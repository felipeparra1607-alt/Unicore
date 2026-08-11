from src.handoff import (
    build_handoff_request,
)
from src.job_manager import (
    JobManager,
)
from src.job_worker import (
    JobWorker,
    WORKER_MODE_LIFECYCLE_ONLY,
)
from src.runtime_context import (
    build_runtime_context,
)


def create_write_job(
    *,
    conversation_id: str,
    allow_writes: bool,
):
    handoff = build_handoff_request(
        kind="artifact",
        objective="Prueba de permisos",
        context_summary=(
            "Job técnico para comprobar "
            "la política de escritura."
        ),
        expected_output=(
            "Confirmar comportamiento "
            "de permisos."
        ),
        requires_write=True,
    )

    runtime_context = (
        build_runtime_context(
            conversation_id=(
                conversation_id
            ),
            allow_writes=(
                allow_writes
            ),
            allowed_paths=[
                "data",
            ],
        )
    )

    return (
        JobManager()
        .create_from_handoff(
            handoff,
            runtime_context=(
                runtime_context
            ),
        )
    )


def main() -> None:
    # ========================================================
    # CASO 1
    # Origen NO permite escribir.
    # Worker tampoco.
    # Debe bloquearse.
    # ========================================================

    job_1 = create_write_job(
        conversation_id=(
            "conv_permissions_1"
        ),
        allow_writes=False,
    )

    result_1 = JobWorker(
        allow_writes=False,
        mode=(
            WORKER_MODE_LIFECYCLE_ONLY
        ),
    ).run(
        job_1.job_id
    )

    assert result_1["ok"] is False

    assert (
        "permisos"
        in result_1["error"].casefold()
    )

    # ========================================================
    # CASO 2
    # Origen NO permite escribir.
    # Worker SÍ.
    # También debe bloquearse:
    # el Worker no puede escalar permisos.
    # ========================================================

    job_2 = create_write_job(
        conversation_id=(
            "conv_permissions_2"
        ),
        allow_writes=False,
    )

    result_2 = JobWorker(
        allow_writes=True,
        mode=(
            WORKER_MODE_LIFECYCLE_ONLY
        ),
    ).run(
        job_2.job_id
    )

    assert result_2["ok"] is False

    assert (
        "origen"
        in result_2["error"].casefold()
    )

    # ========================================================
    # CASO 3
    # Origen permite escribir.
    # Worker NO.
    # Debe bloquearse.
    # ========================================================

    job_3 = create_write_job(
        conversation_id=(
            "conv_permissions_3"
        ),
        allow_writes=True,
    )

    result_3 = JobWorker(
        allow_writes=False,
        mode=(
            WORKER_MODE_LIFECYCLE_ONLY
        ),
    ).run(
        job_3.job_id
    )

    assert result_3["ok"] is False

    assert (
        "worker"
        in result_3["error"].casefold()
    )

    # ========================================================
    # CASO 4
    # Ambos permiten escritura.
    # Debe ejecutarse.
    # ========================================================

    job_4 = create_write_job(
        conversation_id=(
            "conv_permissions_4"
        ),
        allow_writes=True,
    )

    result_4 = JobWorker(
        allow_writes=True,
        mode=(
            WORKER_MODE_LIFECYCLE_ONLY
        ),
    ).run(
        job_4.job_id
    )

    assert result_4["ok"] is True

    runtime_context = (
        result_4[
            "result"
        ][
            "runtime_context"
        ]
    )

    assert (
        runtime_context[
            "conversation_id"
        ]
        == "conv_permissions_4"
    )

    assert (
        runtime_context[
            "job_id"
        ]
        == job_4.job_id
    )

    assert (
        runtime_context[
            "allow_writes"
        ]
        is True
    )

    print(
        "job permissions smoke: OK"
    )


if __name__ == "__main__":
    main()