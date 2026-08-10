from __future__ import annotations

import argparse
import asyncio
import json

from dataclasses import dataclass

from src.unicore_agent import (
    UniCoreAgent,
)


@dataclass(frozen=True)
class HandoffEvalCase:
    name: str
    request: str
    should_handoff: bool
    expected_kind: str | None = None


HANDOFF_CASES = (
    HandoffEvalCase(
        name="simple_tasks_no_handoff",
        request=(
            "¿Qué tareas académicas tengo pendientes?"
        ),
        should_handoff=False,
    ),

    HandoffEvalCase(
        name="artifact_handoff",
        request=(
            "Analiza todos mis documentos académicos "
            "y crea una guía exhaustiva de estudio que "
            "integre todo el contenido importante del curso. "
            "Quiero un resultado largo y estructurado, no "
            "una respuesta breve."
        ),
        should_handoff=True,
        expected_kind="artifact",
    ),

    HandoffEvalCase(
        name="long_analysis_handoff",
        request=(
            "Haz un análisis exhaustivo de todo mi "
            "rendimiento académico del semestre, cruzando "
            "notas, evaluaciones, tareas, knowledge map y "
            "sesiones de estudio para detectar patrones, "
            "riesgos y prioridades. Quiero un informe "
            "detallado y amplio."
        ),
        should_handoff=True,
        expected_kind="long_analysis",
    ),
)


def evaluate_result(
    case: HandoffEvalCase,
    result: dict,
) -> dict:
    actual_status = (
        result.get(
            "status"
        )
    )

    did_handoff = (
        actual_status
        == "handoff_requested"
    )

    handoff = (
        result.get(
            "handoff"
        )
        or {}
    )

    actual_kind = (
        handoff.get(
            "kind"
        )
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
        "name": (
            "handoff_decision_correct"
        ),
        "passed": (
            did_handoff
            == case.should_handoff
        ),
        "detail": {
            "expected_handoff": (
                case.should_handoff
            ),
            "actual_handoff": (
                did_handoff
            ),
        },
    })

    if (
        case.should_handoff
    ):
        checks.append({
            "name": (
                "handoff_kind_correct"
            ),
            "passed": (
                actual_kind
                == case.expected_kind
            ),
            "detail": {
                "expected": (
                    case.expected_kind
                ),
                "actual": (
                    actual_kind
                ),
            },
        })

        checks.append({
            "name": (
                "handoff_objective_present"
            ),
            "passed": bool(
                str(
                    handoff.get(
                        "objective",
                        "",
                    )
                ).strip()
            ),
            "detail": (
                handoff.get(
                    "objective"
                )
            ),
        })

        checks.append({
            "name": (
                "handoff_context_present"
            ),
            "passed": bool(
                str(
                    handoff.get(
                        "context_summary",
                        "",
                    )
                ).strip()
            ),
            "detail": (
                handoff.get(
                    "context_summary"
                )
            ),
        })

        checks.append({
            "name": (
                "handoff_expected_output_present"
            ),
            "passed": bool(
                str(
                    handoff.get(
                        "expected_output",
                        "",
                    )
                ).strip()
            ),
            "detail": (
                handoff.get(
                    "expected_output"
                )
            ),
        })

    failed_checks = [
        check
        for check in checks
        if not check[
            "passed"
        ]
    ]

    usage = (
        result.get(
            "usage",
            {},
        )
    )

    return {
        "name": (
            case.name
        ),
        "request": (
            case.request
        ),
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
        "expected_handoff": (
            case.should_handoff
        ),
        "expected_kind": (
            case.expected_kind
        ),
        "actual_status": (
            actual_status
        ),
        "handoff": (
            handoff
            if did_handoff
            else None
        ),
        "answer": (
            result.get(
                "answer"
            )
        ),
        "checks": (
            checks
        ),
        "usage": (
            usage
        ),
    }


async def run_case(
    case: HandoffEvalCase,
    provider: str | None,
) -> dict:
    agent = UniCoreAgent(
        provider_name=provider,
        allow_writes=False,
        prompt_version="v3",
    )

    result = await agent.run(
        case.request
    )

    return evaluate_result(
        case,
        result,
    )


async def run_suite(
    provider: str | None,
    selected_case: str | None,
) -> dict:
    cases = list(
        HANDOFF_CASES
    )

    if selected_case:
        cases = [
            case
            for case in cases
            if case.name
            == selected_case
        ]

        if not cases:
            return {
                "ok": False,
                "error": (
                    "Caso de Handoff inexistente"
                ),
                "available_cases": [
                    case.name
                    for case
                    in HANDOFF_CASES
                ],
            }

    results = []

    for case in cases:
        print(
            (
                "Evaluando Handoff: "
                f"{case.name}..."
            ),
            flush=True,
        )

        result = await run_case(
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

    total_tokens = sum(
        (
            result.get(
                "usage",
                {},
            ).get(
                "total_tokens",
                0,
            )
        )
        for result in results
    )

    total_cost = sum(
        (
            result.get(
                "usage",
                {},
            ).get(
                "estimated_cost_usd",
                0.0,
            )
        )
        for result in results
    )

    return {
        "ok": (
            passed_count
            == len(results)
        ),
        "summary": {
            "case_count": (
                len(results)
            ),
            "passed_count": (
                passed_count
            ),
            "failed_count": (
                len(results)
                - passed_count
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
                else 0.0
            ),
            "total_tokens": (
                total_tokens
            ),
            "estimated_cost_usd": (
                round(
                    total_cost,
                    8,
                )
            ),
        },
        "results": (
            results
        ),
    }


def build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evals de Handoff para UniCore"
        )
    )

    parser.add_argument(
        "--provider",
        default=None,
    )

    parser.add_argument(
        "--case",
        default=None,
    )

    parser.add_argument(
        "--list",
        action="store_true",
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
                        "name": (
                            case.name
                        ),
                        "request": (
                            case.request
                        ),
                        "should_handoff": (
                            case.should_handoff
                        ),
                        "expected_kind": (
                            case.expected_kind
                        ),
                    }
                    for case
                    in HANDOFF_CASES
                ],
                ensure_ascii=False,
                indent=2,
            )
        )

        return

    result = await run_suite(
        provider=(
            args.provider
        ),
        selected_case=(
            args.case
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
