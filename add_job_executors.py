from __future__ import annotations

import py_compile
import shutil

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parent
)

WORKER_PATH = (
    ROOT
    / "src"
    / "job_worker.py"
)

BACKUP_PATH = (
    ROOT
    / "src"
    / "job_worker_before_extra_executors.py"
)


if not WORKER_PATH.exists():
    raise FileNotFoundError(
        f"No existe: {WORKER_PATH}"
    )


source = WORKER_PATH.read_text(
    encoding="utf-8"
)


if "_execute_long_analysis" in source:
    print(
        "Los executors adicionales ya parecen instalados."
    )
    raise SystemExit(0)


shutil.copy2(
    WORKER_PATH,
    BACKUP_PATH,
)


# ============================================================
# INSERTAR HELPERS ANTES DE EXECUTE
# ============================================================


marker = """    # ========================================================
    # EXECUTE
    # ========================================================
"""


new_methods = r'''    # ========================================================
    # DATOS PARA LONG ANALYSIS
    # ========================================================


    async def _get_long_analysis_evidence(
        self,
        job,
    ) -> str:
        """
        Recupera estado académico estructurado.

        Evitamos loops de agente y usamos
        Resources MCP directamente.
        """

        candidate_uris = [
            "unicore://subjects",
            "unicore://tasks",
            "unicore://today",
        ]

        observations = []

        async with (
            UniCoreMCPClient()
            as client
        ):
            for uri in candidate_uris:
                try:
                    result = (
                        await client.read_resource(
                            uri
                        )
                    )

                    observations.append({
                        "uri": uri,
                        "result": result,
                    })

                except Exception as error:
                    observations.append({
                        "uri": uri,
                        "error": str(error),
                    })

        return compact_text(
            observations,
            maximum_characters=9000,
        )


    def _build_long_analysis_request(
        self,
        *,
        job,
        evidence: str,
    ) -> GenerationRequest:
        system_message = """
Eres el executor de análisis académicos largos de UniCore.

La evidencia ya ha sido recuperada.
Tu trabajo es analizarla, no decidir Tools.

REGLAS:
1. Basa los hechos en la evidencia.
2. Separa hechos observados de inferencias.
3. Identifica patrones, riesgos y prioridades.
4. No inventes datos ausentes.
5. No devuelvas JSON.
6. Produce un análisis estructurado y útil.
""".strip()

        user_message = f"""
OBJETIVO:
{job.objective}

CONTEXTO:
{job.context_summary}

RESULTADO ESPERADO:
{job.expected_output}

EVIDENCIA ACADÉMICA:
{evidence}

Genera el análisis final.
""".strip()

        return GenerationRequest(
            system_message=system_message,
            user_message=user_message,
            maximum_output_tokens=1800,
        )


    async def _execute_long_analysis(
        self,
        job,
    ) -> dict:
        evidence = (
            await self
            ._get_long_analysis_evidence(
                job
            )
        )

        settings = (
            get_ai_settings()
        )

        provider = (
            create_provider(
                settings=settings,
                requested_provider=(
                    self.provider_name
                ),
            )
        )

        request = (
            self
            ._build_long_analysis_request(
                job=job,
                evidence=evidence,
            )
        )

        generation = (
            await asyncio.to_thread(
                provider.generate,
                request,
            )
        )

        if not generation.ok:
            raise RuntimeError(
                generation.error
                or "Falló long_analysis"
            )

        answer = str(
            generation.text
            or ""
        ).strip()

        if not answer:
            raise RuntimeError(
                "long_analysis devolvió vacío"
            )

        return {
            "worker_mode": (
                WORKER_MODE_EXECUTE
            ),
            "executor": (
                "long_analysis_direct"
            ),
            "job_kind": (
                job.kind
            ),
            "answer": answer,
            "evidence_characters": (
                len(evidence)
            ),
            "usage": {
                "model_calls": 1,
                "input_tokens": (
                    generation.input_tokens
                    or 0
                ),
                "output_tokens": (
                    generation.output_tokens
                    or 0
                ),
                "total_tokens": (
                    generation.total_tokens
                    or 0
                ),
                "estimated_cost_usd": (
                    generation
                    .estimated_total_cost_usd
                    or 0.0
                ),
            },
        }


    # ========================================================
    # RESEARCH
    # ========================================================


    async def _get_research_evidence(
        self,
        job,
    ) -> str:
        query = (
            job.objective
            + "\\n\\n"
            + job.expected_output
        )

        arguments = {
            "query": query,
            "mode": "extractive",
            "maximum_sources": 8,
            "maximum_context_characters": 9000,
            "maximum_sentences": 14,
            "minimum_score": 0.2,
            "semantic_weight": 0.75,
            "redundancy_threshold": 0.8,
        }

        async with (
            UniCoreMCPClient()
            as client
        ):
            result = (
                await client.call_tool(
                    "answer_with_rag",
                    arguments,
                )
            )

        return compact_text(
            result,
            maximum_characters=9000,
        )


    def _build_research_request(
        self,
        *,
        job,
        evidence: str,
    ) -> GenerationRequest:
        system_message = """
Eres el executor de research académico de UniCore.

La evidencia relevante ya ha sido recuperada.

REGLAS:
1. Sintetiza únicamente a partir de la evidencia.
2. No inventes información externa.
3. Separa hechos de inferencias.
4. Señala cuando la evidencia sea insuficiente.
5. No devuelvas JSON.
6. Produce una síntesis clara, organizada y útil.
""".strip()

        user_message = f"""
OBJETIVO:
{job.objective}

CONTEXTO:
{job.context_summary}

RESULTADO ESPERADO:
{job.expected_output}

EVIDENCIA RECUPERADA:
{evidence}

Genera la síntesis final.
""".strip()

        return GenerationRequest(
            system_message=system_message,
            user_message=user_message,
            maximum_output_tokens=1800,
        )


    async def _execute_research(
        self,
        job,
    ) -> dict:
        evidence = (
            await self
            ._get_research_evidence(
                job
            )
        )

        settings = (
            get_ai_settings()
        )

        provider = (
            create_provider(
                settings=settings,
                requested_provider=(
                    self.provider_name
                ),
            )
        )

        request = (
            self
            ._build_research_request(
                job=job,
                evidence=evidence,
            )
        )

        generation = (
            await asyncio.to_thread(
                provider.generate,
                request,
            )
        )

        if not generation.ok:
            raise RuntimeError(
                generation.error
                or "Falló research"
            )

        answer = str(
            generation.text
            or ""
        ).strip()

        if not answer:
            raise RuntimeError(
                "research devolvió vacío"
            )

        return {
            "worker_mode": (
                WORKER_MODE_EXECUTE
            ),
            "executor": (
                "research_direct"
            ),
            "job_kind": (
                job.kind
            ),
            "answer": answer,
            "evidence_characters": (
                len(evidence)
            ),
            "usage": {
                "model_calls": 1,
                "input_tokens": (
                    generation.input_tokens
                    or 0
                ),
                "output_tokens": (
                    generation.output_tokens
                    or 0
                ),
                "total_tokens": (
                    generation.total_tokens
                    or 0
                ),
                "estimated_cost_usd": (
                    generation
                    .estimated_total_cost_usd
                    or 0.0
                ),
            },
        }


'''


if marker not in source:
    raise RuntimeError(
        "No encontré el bloque EXECUTE."
    )


source = source.replace(
    marker,
    new_methods + marker,
    1,
)


# ============================================================
# CAMBIAR DISPATCH
# ============================================================


old_dispatch = '''            if (
                running_job.kind
                == "artifact"
            ):
                worker_result = (
                    await self
                    ._execute_artifact(
                        running_job
                    )
                )

            else:
                raise NotImplementedError(
                    (
                        "El executor real para Jobs "
                        f"de tipo {running_job.kind!r} "
                        "todavía no está implementado"
                    )
                )
'''


new_dispatch = '''            if (
                running_job.kind
                == "artifact"
            ):
                worker_result = (
                    await self
                    ._execute_artifact(
                        running_job
                    )
                )

            elif (
                running_job.kind
                == "long_analysis"
            ):
                worker_result = (
                    await self
                    ._execute_long_analysis(
                        running_job
                    )
                )

            elif (
                running_job.kind
                == "research"
            ):
                worker_result = (
                    await self
                    ._execute_research(
                        running_job
                    )
                )

            else:
                raise NotImplementedError(
                    (
                        "Executor no implementado "
                        f"para {running_job.kind!r}"
                    )
                )
'''


if old_dispatch not in source:
    raise RuntimeError(
        "No encontré el dispatch actual."
    )


source = source.replace(
    old_dispatch,
    new_dispatch,
    1,
)


WORKER_PATH.write_text(
    source,
    encoding="utf-8",
)


try:
    py_compile.compile(
        str(
            WORKER_PATH
        ),
        doraise=True,
    )

except Exception:
    shutil.copy2(
        BACKUP_PATH,
        WORKER_PATH,
    )
    raise


print()
print(
    "Executors añadidos:"
)

print(
    "- artifact_direct"
)

print(
    "- long_analysis_direct"
)

print(
    "- research_direct"
)

print()
print(
    "Compilación: OK"
)