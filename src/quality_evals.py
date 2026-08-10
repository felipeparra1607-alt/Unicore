from __future__ import annotations

import argparse
import asyncio
import json
import re
import unicodedata

from dataclasses import dataclass
from typing import Any

from src.ai_config import get_ai_settings
from src.providers import create_provider
from src.providers.base import GenerationRequest
from src.unicore_agent import (
    UniCoreAgent,
    compact_text,
    extract_json_object,
)

from src.agent_prompts import (
    DEFAULT_PROMPT_VERSION,
    SUPPORTED_PROMPT_VERSIONS,
)
from src.unicore_client import UniCoreMCPClient


# ============================================================
# CASOS DETERMINISTAS
# ============================================================


@dataclass(frozen=True)
class QualityCase:
    name: str
    request: str

    required_fact_groups: tuple[
        tuple[str, ...],
        ...
    ] = ()

    forbidden_expressions: tuple[
        str,
        ...
    ] = ()

    minimum_answer_characters: int = 20
    maximum_answer_characters: int = 2500


QUALITY_CASES = [

    QualityCase(
        name="grade_quality",
        request=(
            "¿Cómo voy de nota en Dirección Estratégica?"
        ),
        required_fact_groups=(
            (
                "8,0",
                "8.0",
                "8 sobre 10",
                "8/10",
            ),
            (
                "30%",
                "30 %",
            ),
            (
                "2,4",
                "2.4",
                "24%",
                "24 %",
                "24 puntos porcentuales",
            ),
            (
                "objetivo",
                "meta",
                "nota final de 8,0",
                "nota final de 8.0",
                "mantener una nota final de 8,0",
                "mantener una nota final de 8.0",
                "necesitas promediar un 8,0",
                "necesitas promediar un 8.0",
                "terminar con un 8,0",
                "terminar con un 8.0",
                "mantener una media de 8,0",
                "mantener una media de 8.0",
            ),
        ),
    ),

    QualityCase(
        name="planning_quality",
        request=(
            "Tengo 60 minutos libres. "
            "¿Qué debería estudiar o hacer ahora?"
        ),
        required_fact_groups=(
            (
                "preparar trabajo",
                "trabajo de direccion estrategica",
            ),
            (
                "workflows",
                "agentes",
            ),
            (
                "30 minutos",
                "30 min",
            ),
        ),
    ),

    QualityCase(
        name="pending_tasks_quality",
        request=(
            "¿Qué tareas académicas tengo pendientes?"
        ),
        required_fact_groups=(
            (
                "preparar trabajo",
                "trabajo de direccion estrategica",
            ),
            (
                "workflows",
                "agentes",
            ),
        ),
    ),

    QualityCase(
        name="simulate_grade_quality",
        request=(
            "Quiero simular qué pasaría con mi nota "
            "de Dirección Estratégica si saco un 9 "
            "en una evaluación pendiente."
        ),
        required_fact_groups=(
            (
                "9",
            ),
            (
                "2,7",
                "2.7",
                "27%",
                "27 %",
            ),
            (
                "5,1",
                "5.1",
            ),
        ),
        forbidden_expressions=(
            "he modificado tu nota",
            "he guardado la nota",
            "he actualizado tu calificacion",
        ),
    ),

    QualityCase(
        name="professor_quality",
        request=(
            "¿Qué información tienes del profesor "
            "de Dirección Estratégica?"
        ),
        minimum_answer_characters=30,
    ),
]


# ============================================================
# CASO SEMÁNTICO / RAG
# ============================================================


RAG_SEMANTIC_CASE_NAME = (
    "rag_workflow_vs_agent_quality"
)

RAG_SEMANTIC_REQUEST = (
    "Explícame según mis documentos cuál es "
    "la diferencia entre un workflow y un agente."
)


# ============================================================
# NORMALIZACIÓN
# ============================================================


def normalize_text(
    value: str,
) -> str:
    text = value.casefold().strip()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(
            character
        )
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


# ============================================================
# GRADER DETERMINISTA
# ============================================================


def grade_answer(
    case: QualityCase,
    result: dict,
) -> dict:
    answer = str(
        result.get(
            "answer",
            "",
        )
        or ""
    ).strip()

    normalized_answer = normalize_text(
        answer
    )

    checks = []

    checks.append({
        "name": (
            "agent_finished_successfully"
        ),
        "passed": (
            result.get("ok")
            is True
        ),
        "detail": (
            result.get("error")
        ),
    })

    checks.append({
        "name": "answer_not_empty",
        "passed": bool(
            answer
        ),
        "detail": (
            len(answer)
        ),
    })

    checks.append({
        "name": (
            "minimum_answer_length"
        ),
        "passed": (
            len(answer)
            >= case.minimum_answer_characters
        ),
        "detail": {
            "minimum": (
                case.minimum_answer_characters
            ),
            "actual": (
                len(answer)
            ),
        },
    })

    checks.append({
        "name": (
            "maximum_answer_length"
        ),
        "passed": (
            len(answer)
            <= case.maximum_answer_characters
        ),
        "detail": {
            "maximum": (
                case.maximum_answer_characters
            ),
            "actual": (
                len(answer)
            ),
        },
    })

    fact_results = []

    for group_number, alternatives in enumerate(
        case.required_fact_groups,
        start=1,
    ):
        normalized_alternatives = [
            normalize_text(
                alternative
            )
            for alternative in alternatives
        ]

        matched = [
            alternative
            for alternative
            in normalized_alternatives
            if alternative
            in normalized_answer
        ]

        passed = bool(
            matched
        )

        fact_results.append({
            "group": group_number,
            "passed": passed,
            "alternatives": list(
                alternatives
            ),
            "matched": matched,
        })

        checks.append({
            "name": (
                f"required_fact_group_"
                f"{group_number}"
            ),
            "passed": passed,
            "detail": {
                "accepted": list(
                    alternatives
                ),
                "matched": (
                    matched
                ),
            },
        })

    forbidden_matches = []

    for expression in (
        case.forbidden_expressions
    ):
        normalized_expression = (
            normalize_text(
                expression
            )
        )

        if (
            normalized_expression
            in normalized_answer
        ):
            forbidden_matches.append(
                expression
            )

    checks.append({
        "name": (
            "forbidden_expressions_absent"
        ),
        "passed": (
            len(
                forbidden_matches
            )
            == 0
        ),
        "detail": (
            forbidden_matches
        ),
    })

    prompt_leak_indicators = (
        "tools disponibles para este agente",
        "resources disponibles",
        "debes responder siempre con un unico objeto json",
        "estas instrucciones internas",
    )

    prompt_leaks = [
        indicator
        for indicator
        in prompt_leak_indicators
        if normalize_text(
            indicator
        )
        in normalized_answer
    ]

    checks.append({
        "name": "no_prompt_leak",
        "passed": (
            len(prompt_leaks)
            == 0
        ),
        "detail": prompt_leaks,
    })

    failed_checks = [
        check
        for check in checks
        if not check[
            "passed"
        ]
    ]

    usage = result.get(
        "usage",
        {},
    )

    return {
        "name": case.name,
        "grader_type": (
            "deterministic"
        ),
        "request": case.request,
        "passed": (
            len(failed_checks)
            == 0
        ),
        "failed_check_count": (
            len(failed_checks)
        ),
        "answer": answer,
        "checks": checks,
        "fact_results": (
            fact_results
        ),
        "usage": {
            "model_calls": (
                usage.get(
                    "model_calls",
                    0,
                )
            ),
            "input_tokens": (
                usage.get(
                    "input_tokens",
                    0,
                )
            ),
            "output_tokens": (
                usage.get(
                    "output_tokens",
                    0,
                )
            ),
            "total_tokens": (
                usage.get(
                    "total_tokens",
                    0,
                )
            ),
            "estimated_cost_usd": (
                usage.get(
                    "estimated_cost_usd",
                    0.0,
                )
            ),
        },
    }


# ============================================================
# EVIDENCIA RAG PARA EL GRADER SEMÁNTICO
# ============================================================


async def get_rag_evidence(
    query: str,
) -> str:
    """
    Recupera evidencia de UniCore sin usar
    un segundo LLM.

    El grader semántico juzga la respuesta
    contra esta evidencia real del RAG.
    """

    arguments = {
        "query": query,
        "mode": "extractive",
        "maximum_sources": 5,
        "maximum_context_characters": 6000,
        "maximum_sentences": 8,
        "minimum_score": 0.2,
        "semantic_weight": 0.75,
        "redundancy_threshold": 0.8,
    }

    async with UniCoreMCPClient() as client:
        result = await client.call_tool(
            "answer_with_rag",
            arguments,
        )

    return compact_text(
        result,
        maximum_characters=7000,
    )


# ============================================================
# PROMPT DEL GRADER SEMÁNTICO
# ============================================================


def build_semantic_grader_message(
    request: str,
    answer: str,
    evidence: str,
) -> str:
    return f"""
Eres un grader de calidad para un sistema académico.

Evalúa SOLAMENTE la respuesta del agente usando:
1. la petición del usuario;
2. la evidencia recuperada de los documentos.

No uses conocimientos externos para completar
ni corregir la evidencia.

PETICIÓN DEL USUARIO:
{request}

RESPUESTA DEL AGENTE:
{answer}

EVIDENCIA RAG:
{evidence}

Puntúa cada dimensión con 0, 1 o 2:

groundedness:
0 = contiene afirmaciones importantes no respaldadas
    o contradice la evidencia.
1 = mayormente respaldada, con alguna imprecisión menor.
2 = las afirmaciones importantes están respaldadas.

correctness:
0 = comparación incorrecta o engañosa.
1 = esencialmente correcta pero con alguna imprecisión.
2 = correcta según la evidencia.

completeness:
0 = no explica la diferencia central.
1 = explica la diferencia central pero omite un aspecto útil.
2 = explica claramente ambos conceptos y su diferencia.

relevance:
0 = no responde realmente a la pregunta.
1 = responde pero con contenido innecesario o poco claro.
2 = respuesta directa, clara y útil.

Devuelve SOLO un objeto JSON válido con esta forma:

{{
  "groundedness": 0,
  "correctness": 0,
  "completeness": 0,
  "relevance": 0,
  "unsupported_claims": [],
  "missing_points": [],
  "reason": "explicación breve"
}}

No devuelvas Markdown.
""".strip()


# ============================================================
# GRADER SEMÁNTICO
# ============================================================


async def run_semantic_rag_case(
    provider_name: str | None,
    prompt_version: str,
) -> dict:
    agent = UniCoreAgent(
        provider_name=provider_name,
        allow_writes=False,
        prompt_version=(
            prompt_version
        ),
    )

    agent_result = await agent.run(
        RAG_SEMANTIC_REQUEST
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
        return {
            "name": (
                RAG_SEMANTIC_CASE_NAME
            ),
            "grader_type": (
                "semantic"
            ),
            "request": (
                RAG_SEMANTIC_REQUEST
            ),
            "passed": False,
            "failed_check_count": 1,
            "answer": answer,
            "checks": [
                {
                    "name": (
                        "agent_finished_successfully"
                    ),
                    "passed": False,
                    "detail": (
                        agent_result.get(
                            "error"
                        )
                    ),
                }
            ],
            "semantic_grade": None,
            "usage": {
                "agent": (
                    agent_result.get(
                        "usage",
                        {},
                    )
                ),
                "grader": {},
                "combined": (
                    agent_result.get(
                        "usage",
                        {},
                    )
                ),
            },
        }

    evidence = await get_rag_evidence(
        RAG_SEMANTIC_REQUEST
    )

    settings = get_ai_settings()

    provider = create_provider(
        settings=settings,
        requested_provider=(
            provider_name
        ),
    )

    grader_request = GenerationRequest(
        system_message=(
            "Eres un grader estricto. "
            "Devuelve únicamente JSON válido."
        ),
        user_message=(
            build_semantic_grader_message(
                request=(
                    RAG_SEMANTIC_REQUEST
                ),
                answer=answer,
                evidence=evidence,
            )
        ),
        maximum_output_tokens=350,
    )

    grader_results = []

    semantic_grade = None
    grader_error = None

    for grader_generation_attempt in (
        1,
        2,
    ):
        if (
            grader_generation_attempt
            == 1
        ):
            current_grader_request = (
                grader_request
            )

        else:
            current_grader_request = (
                GenerationRequest(
                    system_message=(
                        "Eres un grader estricto. "
                        "Devuelve únicamente JSON válido."
                    ),
                    user_message=(
                        build_semantic_grader_message(
                            request=(
                                RAG_SEMANTIC_REQUEST
                            ),
                            answer=answer,
                            evidence=evidence,
                        )
                        + "\n\n"
                        + "CORRECCIÓN DE FORMATO:\n"
                        + "La respuesta anterior no pudo "
                        + "interpretarse como un objeto JSON "
                        + "válido. Evalúa otra vez la misma "
                        + "respuesta usando exactamente la misma "
                        + "rúbrica y devuelve únicamente un "
                        + "objeto JSON válido. "
                        + "No uses Markdown ni texto adicional."
                    ),
                    maximum_output_tokens=350,
                )
            )

        grader_result = await asyncio.to_thread(
            provider.generate,
            current_grader_request,
        )

        grader_results.append(
            grader_result
        )

        if not grader_result.ok:
            grader_error = (
                grader_result.error
                or "Falló el grader semántico"
            )

            continue

        try:
            semantic_grade = (
                extract_json_object(
                    grader_result.text
                    or ""
                )
            )

            break

        except Exception as error:
            grader_error = str(
                error
            )

            continue

    grader_input_tokens = sum(
        result.input_tokens
        or 0
        for result in grader_results
    )

    grader_output_tokens = sum(
        result.output_tokens
        or 0
        for result in grader_results
    )

    grader_total_tokens = sum(
        result.total_tokens
        or 0
        for result in grader_results
    )

    grader_cost = sum(
        result.estimated_total_cost_usd
        or 0.0
        for result in grader_results
    )

    if semantic_grade is None:
        return {
            "name": (
                RAG_SEMANTIC_CASE_NAME
            ),
            "grader_type": (
                "semantic"
            ),
            "prompt_version": (
                prompt_version
            ),
            "request": (
                RAG_SEMANTIC_REQUEST
            ),
            "passed": False,
            "failed_check_count": 1,
            "answer": answer,
            "checks": [
                {
                    "name": (
                        "semantic_grader_valid_json"
                    ),
                    "passed": False,
                    "detail": (
                        grader_error
                    ),
                }
            ],
            "semantic_grade": None,
            "usage": {
                "agent": (
                    agent_result.get(
                        "usage",
                        {},
                    )
                ),
                "grader": {
                    "model_calls": (
                        len(
                            grader_results
                        )
                    ),
                    "input_tokens": (
                        grader_input_tokens
                    ),
                    "output_tokens": (
                        grader_output_tokens
                    ),
                    "total_tokens": (
                        grader_total_tokens
                    ),
                    "estimated_cost_usd": (
                        round(
                            grader_cost,
                            8,
                        )
                    ),
                },
            },
        }

    dimensions = (
        "groundedness",
        "correctness",
        "completeness",
        "relevance",
    )

    scores: dict[str, int] = {}

    for dimension in dimensions:
        raw_value = semantic_grade.get(
            dimension
        )

        try:
            score = int(
                raw_value
            )

        except (
            TypeError,
            ValueError,
        ):
            score = -1

        scores[
            dimension
        ] = score

    total_score = sum(
        max(
            0,
            score,
        )
        for score in scores.values()
    )

    dimensions_valid = all(
        score in {
            0,
            1,
            2,
        }
        for score in scores.values()
    )

    no_zero_dimensions = all(
        score >= 1
        for score in scores.values()
    )

    passed = (
        dimensions_valid
        and no_zero_dimensions
        and total_score >= 7
    )

    checks = [
        {
            "name": (
                "semantic_grader_completed"
            ),
            "passed": True,
            "detail": None,
        },
        {
            "name": (
                "semantic_scores_valid"
            ),
            "passed": (
                dimensions_valid
            ),
            "detail": scores,
        },
        {
            "name": (
                "no_critical_semantic_failure"
            ),
            "passed": (
                no_zero_dimensions
            ),
            "detail": scores,
        },
        {
            "name": (
                "semantic_total_score"
            ),
            "passed": (
                total_score >= 7
            ),
            "detail": {
                "minimum": 7,
                "actual": (
                    total_score
                ),
                "maximum": 8,
            },
        },
    ]

    agent_usage = agent_result.get(
        "usage",
        {},
    )

    grader_usage = {
        "model_calls": (
            len(
                grader_results
            )
        ),
        "input_tokens": (
            grader_input_tokens
        ),
        "output_tokens": (
            grader_output_tokens
        ),
        "total_tokens": (
            grader_total_tokens
        ),
        "estimated_cost_usd": (
            round(
                grader_cost,
                8,
            )
        ),
    }

    combined_usage = {
        "model_calls": (
            agent_usage.get(
                "model_calls",
                0,
            )
            + grader_usage[
                "model_calls"
            ]
        ),
        "input_tokens": (
            agent_usage.get(
                "input_tokens",
                0,
            )
            + grader_usage[
                "input_tokens"
            ]
        ),
        "output_tokens": (
            agent_usage.get(
                "output_tokens",
                0,
            )
            + grader_usage[
                "output_tokens"
            ]
        ),
        "total_tokens": (
            agent_usage.get(
                "total_tokens",
                0,
            )
            + grader_usage[
                "total_tokens"
            ]
        ),
        "estimated_cost_usd": round(
            (
                agent_usage.get(
                    "estimated_cost_usd",
                    0.0,
                )
                + grader_usage[
                    "estimated_cost_usd"
                ]
            ),
            8,
        ),
    }

    failed_checks = [
        check
        for check in checks
        if not check[
            "passed"
        ]
    ]

    return {
        "name": (
            RAG_SEMANTIC_CASE_NAME
        ),
        "grader_type": (
            "semantic"
        ),
        "prompt_version": (
            prompt_version
        ),
        "request": (
            RAG_SEMANTIC_REQUEST
        ),
        "passed": passed,
        "failed_check_count": (
            len(failed_checks)
        ),
        "answer": answer,
        "checks": checks,
        "semantic_grade": {
            **semantic_grade,
            "scores": scores,
            "total_score": (
                total_score
            ),
        },
        "evidence_characters": (
            len(evidence)
        ),
        "usage": {
            "agent": agent_usage,
            "grader": grader_usage,
            "combined": combined_usage,
        },
    }


# ============================================================
# EJECUCIÓN DETERMINISTA
# ============================================================


async def run_quality_case(
    case: QualityCase,
    provider: str | None,
    prompt_version: str,
) -> dict:
    agent = UniCoreAgent(
        provider_name=provider,
        allow_writes=False,
        prompt_version=(
            prompt_version
        ),
    )

    result = await agent.run(
        case.request
    )

    return grade_answer(
        case,
        result,
    )


async def run_deterministic_suite(
    provider: str | None = None,
    selected_case: str | None = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> dict:
    cases = QUALITY_CASES

    if selected_case:
        cases = [
            case
            for case in QUALITY_CASES
            if case.name
            == selected_case
        ]

        if not cases:
            return {
                "ok": False,
                "error": (
                    "No existe el caso "
                    "determinista indicado"
                ),
                "available_cases": [
                    case.name
                    for case
                    in QUALITY_CASES
                ],
            }

    results = []

    for case in cases:
        print(
            (
                f"Evaluando calidad: "
                f"{case.name}..."
            ),
            flush=True,
        )

        result = await run_quality_case(
            case,
            provider,
            prompt_version,
        )

        results.append(
            result
        )

    passed_count = sum(
        1
        for result in results
        if result[
            "passed"
        ]
    )

    failed_count = (
        len(results)
        - passed_count
    )

    total_tokens = sum(
        result[
            "usage"
        ][
            "total_tokens"
        ]
        for result in results
    )

    total_cost = sum(
        result[
            "usage"
        ][
            "estimated_cost_usd"
        ]
        for result in results
    )

    return {
        "ok": (
            failed_count == 0
        ),
        "summary": {
            "case_count": (
                len(results)
            ),
            "passed_count": (
                passed_count
            ),
            "failed_count": (
                failed_count
            ),
            "pass_rate_percentage": (
                round(
                    (
                        passed_count
                        / len(results)
                        * 100
                    ),
                    2,
                )
                if results
                else 0
            ),
            "total_tokens": (
                total_tokens
            ),
            "average_tokens_per_case": (
                round(
                    (
                        total_tokens
                        / len(results)
                    ),
                    2,
                )
                if results
                else 0
            ),
            "estimated_cost_usd": round(
                total_cost,
                8,
            ),
        },
        "results": results,
    }


# ============================================================
# CLI
# ============================================================


def build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evals de calidad para UniCore"
        )
    )

    parser.add_argument(
        "--provider",
        default=None,
    )

    parser.add_argument(
        "--case",
        default=None,
        help=(
            "Ejecuta solamente un caso. "
            f"Usa {RAG_SEMANTIC_CASE_NAME} "
            "para el caso semántico RAG."
        ),
    )

    parser.add_argument(
        "--list",
        action="store_true",
    )

    parser.add_argument(
        "--prompt-version",
        choices=(
            SUPPORTED_PROMPT_VERSIONS
        ),
        default=(
            DEFAULT_PROMPT_VERSION
        ),
        help=(
            "Versión del prompt del agente "
            "que se quiere evaluar"
        ),
    )

    return parser


async def async_main(
) -> None:
    parser = build_parser()

    args = parser.parse_args()

    if args.list:
        items = [
            {
                "name": (
                    case.name
                ),
                "grader_type": (
                    "deterministic"
                ),
                "request": (
                    case.request
                ),
            }
            for case in QUALITY_CASES
        ]

        items.append({
            "name": (
                RAG_SEMANTIC_CASE_NAME
            ),
            "grader_type": (
                "semantic"
            ),
            "request": (
                RAG_SEMANTIC_REQUEST
            ),
        })

        print(
            json.dumps(
                items,
                ensure_ascii=False,
                indent=2,
            )
        )

        return

    if (
        args.case
        == RAG_SEMANTIC_CASE_NAME
    ):
        print(
            (
                "Evaluando calidad semántica: "
                f"{RAG_SEMANTIC_CASE_NAME}..."
            ),
            flush=True,
        )

        result = await run_semantic_rag_case(
            provider_name=(
                args.provider
            ),
            prompt_version=(
                args.prompt_version
            ),
        )

        print()

        print(
            json.dumps(
                {
                    "ok": (
                        result[
                            "passed"
                        ]
                    ),
                    "summary": {
                        "case_count": 1,
                        "passed_count": (
                            1
                            if result[
                                "passed"
                            ]
                            else 0
                        ),
                        "failed_count": (
                            0
                            if result[
                                "passed"
                            ]
                            else 1
                        ),
                        "pass_rate_percentage": (
                            100.0
                            if result[
                                "passed"
                            ]
                            else 0.0
                        ),
                    },
                    "results": [
                        result
                    ],
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        return

    result = await run_deterministic_suite(
        provider=args.provider,
        selected_case=args.case,
        prompt_version=(
            args.prompt_version
        ),
    )

    print()

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


def main(
) -> None:
    asyncio.run(
        async_main()
    )


if __name__ == "__main__":
    main()