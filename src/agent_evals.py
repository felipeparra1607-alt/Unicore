from __future__ import annotations

import argparse
import asyncio
import json

from dataclasses import dataclass
from typing import Any

from src.unicore_agent import (
    UniCoreAgent,
)


# ============================================================
# DEFINICIÓN DE CASOS
# ============================================================


@dataclass
class EvalCase:
    name: str
    request: str

    expected_tool: str | None = None

    accepted_tools: tuple[str, ...] = ()

    preferred_tool: str | None = None

    expected_resource_contains: str | None = None

    forbidden_tools: tuple[str, ...] = ()

    allow_writes: bool = False

    maximum_steps: int = 4

    maximum_tool_calls: int | None = None

    maximum_resource_reads: int | None = None

    minimum_model_calls: int | None = None

    maximum_model_calls: int | None = None


# ============================================================
# DATASET V2
# ============================================================
#
# IMPORTANTE:
#
# No buscamos probar si el texto final es "bonito".
#
# Aquí evaluamos:
#
# - selección de capacidades
# - seguridad
# - eficiencia
# - número de pasos
# - comportamiento MCP
#
# La calidad semántica de la respuesta vendrá
# en la siguiente fase con graders.
# ============================================================


EVAL_CASES = [

    # --------------------------------------------------------
    # 1. DECISION ENGINE
    # --------------------------------------------------------

    EvalCase(
        name="decision_engine_60_minutes",
        request=(
            "Tengo 60 minutos libres. "
            "¿Qué debería estudiar o hacer ahora?"
        ),
        expected_tool=(
            "recommend_next_actions"
        ),
        maximum_tool_calls=1,
        maximum_resource_reads=0,
        maximum_model_calls=3,
    ),

    # --------------------------------------------------------
    # 2. KNOWLEDGE MAP
    # --------------------------------------------------------

    EvalCase(
        name="knowledge_map_weak_concepts",
        request=(
            "¿Cómo voy en Dirección Estratégica? "
            "Quiero saber qué conceptos tengo más flojos."
        ),
        expected_resource_contains=(
            "/knowledge"
        ),
        maximum_tool_calls=0,
        maximum_resource_reads=2,
        maximum_model_calls=4,
    ),

    # --------------------------------------------------------
    # 3. RAG ABSTRACTO
    # --------------------------------------------------------

    EvalCase(
        name="rag_workflow_vs_agent",
        request=(
            "Explícame según mis documentos cuál es "
            "la diferencia entre un workflow y un agente."
        ),
        accepted_tools=(
            "answer_with_rag",
            "hybrid_search",
        ),
        preferred_tool=(
            "answer_with_rag"
        ),
        maximum_tool_calls=2,
        maximum_resource_reads=1,
        maximum_model_calls=4,
    ),

    # --------------------------------------------------------
    # 4. ESCRITURA BLOQUEADA
    # --------------------------------------------------------

    EvalCase(
        name="write_task_blocked",
        request=(
            "Créame una tarea para estudiar workflows "
            "mañana durante 30 minutos."
        ),
        forbidden_tools=(
            "create_academic_task",
            "update_academic_task",
            "complete_academic_task",
        ),
        allow_writes=False,
        maximum_tool_calls=0,
        maximum_resource_reads=1,
        maximum_model_calls=3,
    ),

    # --------------------------------------------------------
    # 5. TAREAS
    # --------------------------------------------------------

    EvalCase(
        name="read_pending_tasks",
        request=(
            "¿Qué tareas académicas tengo pendientes?"
        ),
        expected_resource_contains=(
            "tasks"
        ),
        maximum_tool_calls=0,
        maximum_resource_reads=1,
        maximum_model_calls=3,
    ),

    # --------------------------------------------------------
    # 6. DOCUMENTOS
    # --------------------------------------------------------

    EvalCase(
        name="read_documents",
        request=(
            "¿Qué documentos tengo registrados "
            "en UniCore?"
        ),
        expected_resource_contains=(
            "documents"
        ),
        maximum_tool_calls=0,
        maximum_resource_reads=1,
        maximum_model_calls=3,
    ),

    # --------------------------------------------------------
    # 7. NOTAS / ESTADO ACADÉMICO
    # --------------------------------------------------------

    EvalCase(
        name="subject_grade_status",
        request=(
            "¿Cómo voy de nota en Dirección Estratégica?"
        ),
        expected_resource_contains=(
            "/grade"
        ),
        maximum_tool_calls=0,
        maximum_resource_reads=2,
        maximum_model_calls=4,
    ),

    # --------------------------------------------------------
    # 8. EVALUACIONES
    # --------------------------------------------------------

    EvalCase(
        name="subject_assessments",
        request=(
            "¿Qué evaluaciones tengo en "
            "Dirección Estratégica?"
        ),
        expected_resource_contains=(
            "/assessments"
        ),
        maximum_tool_calls=0,
        maximum_resource_reads=2,
        maximum_model_calls=4,
    ),

    # --------------------------------------------------------
    # 9. PROFESOR
    # --------------------------------------------------------

    EvalCase(
        name="subject_professor",
        request=(
            "¿Qué información tienes del profesor "
            "de Dirección Estratégica?"
        ),
        expected_resource_contains=(
            "/professor"
        ),
        maximum_tool_calls=0,
        maximum_resource_reads=2,
        maximum_model_calls=4,
    ),

    # --------------------------------------------------------
    # 10. REPASO
    # --------------------------------------------------------

    EvalCase(
        name="review_plan",
        request=(
            "¿Qué debería repasar ahora de "
            "Dirección Estratégica?"
        ),
        expected_tool=(
            "get_review_plan"
        ),
        maximum_tool_calls=1,
        maximum_resource_reads=2,
        maximum_model_calls=4,
    ),

    # --------------------------------------------------------
    # 11. SIMULACIÓN DE NOTA
    # --------------------------------------------------------

    EvalCase(
        name="simulate_grade",
        request=(
            "Quiero simular qué pasaría con mi nota "
            "de Dirección Estratégica si saco un 9 "
            "en una evaluación pendiente."
        ),
        expected_tool=(
            "simulate_assessment_grade"
        ),
        maximum_tool_calls=1,
        maximum_resource_reads=2,
        maximum_model_calls=4,
    ),

    # --------------------------------------------------------
    # 12. ESCRITURA DE ESTUDIO BLOQUEADA
    # --------------------------------------------------------

    EvalCase(
        name="study_session_write_blocked",
        request=(
            "Registra una sesión de estudio de "
            "Dirección Estratégica de 45 minutos."
        ),
        forbidden_tools=(
            "create_study_session",
        ),
        allow_writes=False,
        maximum_tool_calls=0,
        maximum_resource_reads=1,
        maximum_model_calls=3,
    ),
]


# ============================================================
# UTILIDADES
# ============================================================


def flatten_trace(
    trace: list[dict],
) -> dict:
    tool_calls = []
    resource_reads = []

    for item in trace:
        status = item.get(
            "status"
        )

        if status == "tool_called":
            tool_calls.append({
                "tool": item.get(
                    "tool"
                ),
                "arguments": item.get(
                    "arguments"
                ),
            })

        elif status == "resource_read":
            resource_reads.append(
                item.get(
                    "uri"
                )
            )

    return {
        "tool_calls": tool_calls,
        "resource_reads": resource_reads,
    }


def add_check(
    checks: list[dict],
    name: str,
    passed: bool,
    detail: Any = None,
) -> None:
    checks.append({
        "name": name,
        "passed": bool(
            passed
        ),
        "detail": detail,
    })


# ============================================================
# GRADER DETERMINISTA
# ============================================================


def grade_case(
    case: EvalCase,
    result: dict,
) -> dict:
    checks: list[dict] = []

    trace = result.get(
        "trace",
        [],
    )

    flattened = flatten_trace(
        trace
    )

    tool_names = [
        item["tool"]
        for item in flattened[
            "tool_calls"
        ]
    ]

    resource_uris = [
        uri
        for uri in flattened[
            "resource_reads"
        ]
        if uri
    ]

    usage = result.get(
        "usage",
        {},
    )

    model_calls = int(
        usage.get(
            "model_calls",
            0,
        )
        or 0
    )

    # --------------------------------------------------------
    # ÉXITO GLOBAL
    # --------------------------------------------------------

    add_check(
        checks,
        "agent_finished_successfully",
        result.get(
            "ok"
        ) is True,
        result.get(
            "error"
        ),
    )

    # --------------------------------------------------------
    # PASOS
    # --------------------------------------------------------

    add_check(
        checks,
        "within_step_limit",
        (
            result.get(
                "steps_used",
                case.maximum_steps,
            )
            <= case.maximum_steps
        ),
        {
            "maximum": (
                case.maximum_steps
            ),
            "actual": (
                result.get(
                    "steps_used"
                )
            ),
        },
    )

    # --------------------------------------------------------
    # TOOL ESPERADA
    # --------------------------------------------------------

    if (
        case.expected_tool
        is not None
    ):
        add_check(
            checks,
            "expected_tool_used",
            case.expected_tool
            in tool_names,
            {
                "expected": (
                    case.expected_tool
                ),
                "actual": (
                    tool_names
                ),
            },
        )
    if case.accepted_tools:
        accepted_tool_used = any(
            tool_name
            in case.accepted_tools
            for tool_name in tool_names
        )

        add_check(
            checks,
            "accepted_tool_used",
            accepted_tool_used,
            {
                "accepted": list(
                    case.accepted_tools
                ),
                "actual": (
                    tool_names
                ),
            },
        )
    preferred_tool_used = None

    if (
        case.preferred_tool
        is not None
    ):
        preferred_tool_used = (
            case.preferred_tool
            in tool_names
        )

    # --------------------------------------------------------
    # RESOURCE ESPERADO
    # --------------------------------------------------------

    if (
        case.expected_resource_contains
        is not None
    ):
        add_check(
            checks,
            "expected_resource_used",
            any(
                (
                    case.expected_resource_contains
                    in uri
                )
                for uri in resource_uris
            ),
            {
                "expected_contains": (
                    case.expected_resource_contains
                ),
                "actual": (
                    resource_uris
                ),
            },
        )

    # --------------------------------------------------------
    # TOOLS PROHIBIDAS
    # --------------------------------------------------------

    for forbidden_tool in (
        case.forbidden_tools
    ):
        add_check(
            checks,
            (
                "forbidden_tool_absent:"
                f"{forbidden_tool}"
            ),
            forbidden_tool
            not in tool_names,
            tool_names,
        )

    # --------------------------------------------------------
    # PRESUPUESTO DE TOOLS
    # --------------------------------------------------------

    if (
        case.maximum_tool_calls
        is not None
    ):
        add_check(
            checks,
            "tool_call_budget",
            (
                len(
                    tool_names
                )
                <= case.maximum_tool_calls
            ),
            {
                "maximum": (
                    case.maximum_tool_calls
                ),
                "actual": (
                    len(
                        tool_names
                    )
                ),
            },
        )

    # --------------------------------------------------------
    # PRESUPUESTO DE RESOURCES
    # --------------------------------------------------------

    if (
        case.maximum_resource_reads
        is not None
    ):
        add_check(
            checks,
            "resource_read_budget",
            (
                len(
                    resource_uris
                )
                <= case.maximum_resource_reads
            ),
            {
                "maximum": (
                    case.maximum_resource_reads
                ),
                "actual": (
                    len(
                        resource_uris
                    )
                ),
            },
        )

    # --------------------------------------------------------
    # PRESUPUESTO DE LLAMADAS AL MODELO
    # --------------------------------------------------------

    if (
        case.minimum_model_calls
        is not None
    ):
        add_check(
            checks,
            "minimum_model_calls",
            (
                model_calls
                >= case.minimum_model_calls
            ),
            {
                "minimum": (
                    case.minimum_model_calls
                ),
                "actual": (
                    model_calls
                ),
            },
        )

    if (
        case.maximum_model_calls
        is not None
    ):
        add_check(
            checks,
            "model_call_budget",
            (
                model_calls
                <= case.maximum_model_calls
            ),
            {
                "maximum": (
                    case.maximum_model_calls
                ),
                "actual": (
                    model_calls
                ),
            },
        )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    failed_checks = [
        check
        for check in checks
        if not check[
            "passed"
        ]
    ]

    return {
        "name": case.name,
        "request": case.request,
        "passed": (
            len(
                failed_checks
            )
            == 0
        ),
        "failed_check_count": (
            len(
                failed_checks
            )
        ),
        "checks": checks,
        "behavior": {
            "tool_calls": (
                flattened[
                    "tool_calls"
                ]
            ),
            "resource_reads": (
                resource_uris
            ),
            "steps_used": (
                result.get(
                    "steps_used"
                )
            ),
            "preferred_tool": (
                case.preferred_tool
            ),
            "preferred_tool_used": (
                preferred_tool_used
            ),
        },
        "usage": {
            "model_calls": (
                model_calls
            ),
            "mcp_tool_calls": (
                usage.get(
                    "mcp_tool_calls",
                    0,
                )
            ),
            "mcp_resource_reads": (
                usage.get(
                    "mcp_resource_reads",
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
# EJECUCIÓN DE UN CASO
# ============================================================


async def run_eval_case(
    case: EvalCase,
    provider: str | None,
) -> dict:
    agent = UniCoreAgent(
        provider_name=provider,
        maximum_steps=(
            case.maximum_steps
        ),
        allow_writes=(
            case.allow_writes
        ),
    )

    result = await agent.run(
        case.request
    )

    return grade_case(
        case,
        result,
    )


# ============================================================
# EJECUCIÓN DEL SUITE
# ============================================================


async def run_eval_suite(
    provider: str | None = None,
    selected_case: str | None = None,
) -> dict:
    cases = EVAL_CASES

    if (
        selected_case
        is not None
    ):
        cases = [
            case
            for case in EVAL_CASES
            if case.name
            == selected_case
        ]

        if not cases:
            return {
                "ok": False,
                "error": (
                    "No existe el caso indicado"
                ),
                "available_cases": [
                    case.name
                    for case in EVAL_CASES
                ],
            }

    results = []

    for case in cases:
        print(
            f"Ejecutando: {case.name}...",
            flush=True,
        )

        result = await run_eval_case(
            case,
            provider,
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

    total_model_calls = sum(
        result[
            "usage"
        ][
            "model_calls"
        ]
        for result in results
    )

    total_tool_calls = sum(
        result[
            "usage"
        ][
            "mcp_tool_calls"
        ]
        for result in results
    )

    total_resource_reads = sum(
        result[
            "usage"
        ][
            "mcp_resource_reads"
        ]
        for result in results
    )

    total_input_tokens = sum(
        result[
            "usage"
        ][
            "input_tokens"
        ]
        for result in results
    )

    total_output_tokens = sum(
        result[
            "usage"
        ][
            "output_tokens"
        ]
        for result in results
    )

    total_tokens = sum(
        result[
            "usage"
        ][
            "total_tokens"
        ]
        for result in results
    )

    estimated_cost = sum(
        result[
            "usage"
        ][
            "estimated_cost_usd"
        ]
        for result in results
    )

    average_model_calls = (
        round(
            total_model_calls
            / len(results),
            2,
        )
        if results
        else 0
    )

    average_tokens = (
        round(
            total_tokens
            / len(results),
            2,
        )
        if results
        else 0
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
                    passed_count
                    / len(results)
                    * 100,
                    2,
                )
                if results
                else 0
            ),
            "total_model_calls": (
                total_model_calls
            ),
            "average_model_calls_per_case": (
                average_model_calls
            ),
            "total_mcp_tool_calls": (
                total_tool_calls
            ),
            "total_mcp_resource_reads": (
                total_resource_reads
            ),
            "total_input_tokens": (
                total_input_tokens
            ),
            "total_output_tokens": (
                total_output_tokens
            ),
            "total_tokens": (
                total_tokens
            ),
            "average_tokens_per_case": (
                average_tokens
            ),
            "estimated_cost_usd": round(
                estimated_cost,
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
            "Evals deterministas del "
            "agente UniCore"
        )
    )

    parser.add_argument(
        "--provider",
        default=None,
        help=(
            "Proveedor de IA. "
            "Si se omite usa .env"
        ),
    )

    parser.add_argument(
        "--case",
        default=None,
        help=(
            "Ejecuta solamente un caso "
            "por nombre"
        ),
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help=(
            "Lista los casos disponibles "
            "sin ejecutar el agente"
        ),
    )

    return parser


async def async_main(
) -> None:
    parser = build_parser()

    args = parser.parse_args()

    if args.list:
        print(
            json.dumps(
                [
                    {
                        "name": case.name,
                        "request": (
                            case.request
                        ),
                    }
                    for case in EVAL_CASES
                ],
                ensure_ascii=False,
                indent=2,
            )
        )

        return

    result = await run_eval_suite(
        provider=args.provider,
        selected_case=args.case,
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