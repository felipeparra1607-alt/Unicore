from __future__ import annotations

import asyncio

from dataclasses import dataclass

from src.job_manager import (
    JobManager,
)

from src.jobs import (
    JOB_STATUS_PENDING,
    job_to_dict,
)

from src.unicore_agent import (
    UniCoreAgent,
)


# ============================================================
# MODOS
# ============================================================


WORKER_MODE_LIFECYCLE_ONLY = (
    "lifecycle_only"
)

WORKER_MODE_EXECUTE = (
    "execute"
)


SUPPORTED_WORKER_MODES = {
    WORKER_MODE_LIFECYCLE_ONLY,
    WORKER_MODE_EXECUTE,
}


# ============================================================
# PROMPT DEL WORKER
# ============================================================


def build_worker_request(
    *,
    kind: str,
    objective: str,
    context_summary: str,
    expected_output: str,
    source_uris: tuple[str, ...],
) -> str:
    """
    Construye la petición de ejecución para el agente
    usado dentro del Worker.

    Importante:
    el Worker utiliza prompt v2, no v3, para impedir
    Handoffs recursivos.
    """

    sources_text = (
        "\n".join(
            f"- {uri}"
            for uri in source_uris
        )
        if source_uris
        else (
            "- No hay Resources específicos "
            "indicados."
        )
    )

    if kind == "artifact":
        execution_guidance = (
            "El objetivo principal es producir un "
            "resultado estructurado y suficientemente "
            "desarrollado. Recupera primero la evidencia "
            "académica necesaria y después crea el "
            "artefacto solicitado."
        )

    elif kind == "long_analysis":
        execution_guidance = (
            "El objetivo principal es realizar un análisis "
            "profundo. Cruza la información académica "
            "relevante, identifica patrones y separa "
            "claramente hechos observados de inferencias."
        )

    elif kind == "research":
        execution_guidance = (
            "El objetivo principal es investigar y "
            "sintetizar información. Recupera evidencia "
            "relevante mediante las capacidades de UniCore "
            "y construye una síntesis fundamentada."
        )

    else:
        execution_guidance = (
            "Resuelve el objetivo usando las capacidades "
            "académicas disponibles."
        )

    return f"""
Estás ejecutando un Job delegado por UniCore.

Este trabajo ya ha sido aceptado como Job.
NO debes delegarlo de nuevo.
Debes ejecutarlo utilizando Resources y Tools de UniCore
cuando sean necesarios.

TIPO DE JOB:
{kind}

OBJETIVO:
{objective}

CONTEXTO MÍNIMO:
{context_summary}

RESULTADO ESPERADO:
{expected_output}

RESOURCES SUGERIDOS:
{sources_text}

INSTRUCCIONES DE EJECUCIÓN:
{execution_guidance}

Reglas:
1. Usa los datos reales de UniCore.
2. No inventes hechos académicos.
3. Si una afirmación es una inferencia, indícalo.
4. Prioriza los Resources sugeridos cuando sean útiles.
5. Puedes utilizar otros Resources o Tools si son necesarios.
6. No afirmes haber modificado estado salvo que realmente
   haya ocurrido.
7. Devuelve el resultado final solicitado al terminar.
""".strip()


# ============================================================
# WORKER
# ============================================================


@dataclass
class JobWorker:
    """
    Worker local de Jobs.

    lifecycle_only:
        prueba infraestructura sin utilizar un modelo.

    execute:
        ejecuta realmente el trabajo utilizando
        UniCoreAgent con prompt v2.
    """

    allow_writes: bool = False

    mode: str = (
        WORKER_MODE_LIFECYCLE_ONLY
    )

    provider_name: str | None = None

    worker_prompt_version: str = "v2"

    maximum_steps: int = 10


    def __post_init__(
        self,
    ) -> None:
        clean_mode = str(
            self.mode
            or ""
        ).strip().casefold()

        if (
            clean_mode
            not in SUPPORTED_WORKER_MODES
        ):
            raise ValueError(
                "Modo de Worker no soportado: "
                f"{clean_mode}"
            )

        self.mode = clean_mode

        if (
            self.worker_prompt_version
            == "v3"
        ):
            raise ValueError(
                "El Worker no puede utilizar v3 "
                "porque podría generar Handoffs "
                "recursivos"
            )

        self.maximum_steps = max(
            1,
            min(
                int(
                    self.maximum_steps
                ),
                20,
            ),
        )


    # ========================================================
    # VALIDACIÓN COMÚN
    # ========================================================


    def _load_pending_job(
        self,
        job_id: str,
    ):
        manager = (
            JobManager()
        )

        job = manager.get(
            job_id
        )

        if job is None:
            return (
                manager,
                None,
                {
                    "ok": False,
                    "error": (
                        "Job inexistente"
                    ),
                },
            )

        if (
            job.status
            != JOB_STATUS_PENDING
        ):
            return (
                manager,
                job,
                {
                    "ok": False,
                    "error": (
                        "El Job no está pending"
                    ),
                    "job": (
                        job_to_dict(
                            job
                        )
                    ),
                },
            )

        if (
            job.requires_write
            and not self.allow_writes
        ):
            failed_job = (
                manager.fail(
                    job.job_id,
                    (
                        "El Job requiere permisos "
                        "de escritura"
                    ),
                )
            )

            return (
                manager,
                failed_job,
                {
                    "ok": False,
                    "error": (
                        "Job bloqueado por permisos"
                    ),
                    "job": (
                        job_to_dict(
                            failed_job
                        )
                    ),
                },
            )

        return (
            manager,
            job,
            None,
        )


    # ========================================================
    # LIFECYCLE ONLY
    # ========================================================


    def _run_lifecycle_only(
        self,
        job_id: str,
    ) -> dict:
        (
            manager,
            job,
            validation_error,
        ) = self._load_pending_job(
            job_id
        )

        if (
            validation_error
            is not None
        ):
            return validation_error

        running_job = manager.start(
            job.job_id
        )

        result = {
            "message": (
                "Worker lifecycle completado "
                "en modo básico"
            ),
            "job_kind": (
                running_job.kind
            ),
            "objective": (
                running_job.objective
            ),
            "worker_mode": (
                WORKER_MODE_LIFECYCLE_ONLY
            ),
        }

        completed_job = (
            manager.complete(
                running_job.job_id,
                result,
            )
        )

        return {
            "ok": True,
            "job": (
                job_to_dict(
                    completed_job
                )
            ),
            "result": result,
        }


    # ========================================================
    # EJECUCIÓN REAL
    # ========================================================


    async def run_async(
        self,
        job_id: str,
    ) -> dict:
        if (
            self.mode
            == WORKER_MODE_LIFECYCLE_ONLY
        ):
            return (
                self._run_lifecycle_only(
                    job_id
                )
            )

        (
            manager,
            job,
            validation_error,
        ) = self._load_pending_job(
            job_id
        )

        if (
            validation_error
            is not None
        ):
            return validation_error

        running_job = manager.start(
            job.job_id
        )

        try:
            request = (
                build_worker_request(
                    kind=(
                        running_job.kind
                    ),
                    objective=(
                        running_job.objective
                    ),
                    context_summary=(
                        running_job.context_summary
                    ),
                    expected_output=(
                        running_job.expected_output
                    ),
                    source_uris=(
                        running_job.source_uris
                    ),
                )
            )

            agent = UniCoreAgent(
                provider_name=(
                    self.provider_name
                ),
                allow_writes=(
                    self.allow_writes
                    and running_job.requires_write
                ),
                maximum_steps=(
                    self.maximum_steps
                ),
                prompt_version=(
                    self.worker_prompt_version
                ),
            )

            agent_result = (
                await agent.run(
                    request
                )
            )

            answer = str(
                agent_result.get(
                    "answer",
                    "",
                )
                or ""
            ).strip()

            if (
                agent_result.get("ok")
                is not True
                or not answer
            ):
                error = (
                    agent_result.get(
                        "error"
                    )
                    or (
                        "El agente del Worker "
                        "no produjo un resultado"
                    )
                )

                failed_job = (
                    manager.fail(
                        running_job.job_id,
                        error,
                    )
                )

                return {
                    "ok": False,
                    "error": error,
                    "job": (
                        job_to_dict(
                            failed_job
                        )
                    ),
                    "agent_result": (
                        agent_result
                    ),
                }

            worker_result = {
                "worker_mode": (
                    WORKER_MODE_EXECUTE
                ),
                "job_kind": (
                    running_job.kind
                ),
                "answer": answer,
                "prompt_version": (
                    self.worker_prompt_version
                ),
                "usage": (
                    agent_result.get(
                        "usage",
                        {},
                    )
                ),
                "steps_used": (
                    agent_result.get(
                        "steps_used"
                    )
                ),
            }

            completed_job = (
                manager.complete(
                    running_job.job_id,
                    worker_result,
                )
            )

            return {
                "ok": True,
                "job": (
                    job_to_dict(
                        completed_job
                    )
                ),
                "result": (
                    worker_result
                ),
            }

        except Exception as error:
            failed_job = (
                manager.fail(
                    running_job.job_id,
                    str(
                        error
                    ),
                )
            )

            return {
                "ok": False,
                "error": (
                    str(
                        error
                    )
                ),
                "job": (
                    job_to_dict(
                        failed_job
                    )
                ),
            }


    # ========================================================
    # API SÍNCRONA
    # ========================================================


    def run(
        self,
        job_id: str,
    ) -> dict:
        if (
            self.mode
            == WORKER_MODE_LIFECYCLE_ONLY
        ):
            return (
                self._run_lifecycle_only(
                    job_id
                )
            )

        return asyncio.run(
            self.run_async(
                job_id
            )
        )