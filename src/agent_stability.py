from __future__ import annotations

import argparse
import asyncio
import json

from collections import defaultdict

from src.agent_evals import (
    EVAL_CASES,
    run_eval_case,
)


DEFAULT_CASES = [
    "decision_engine_60_minutes",
    "subject_grade_status",
    "rag_workflow_vs_agent",
    "simulate_grade",
]


def get_case_by_name(
    name: str,
):
    for case in EVAL_CASES:
        if case.name == name:
            return case

    raise ValueError(
        f"No existe el caso: {name}"
    )


async def run_stability_suite(
    repeats: int = 3,
    provider: str | None = None,
) -> dict:
    """
    Ejecuta varias veces los casos más importantes
    para medir estabilidad del agente.

    No modifica el prompt ni los graders.
    """

    if repeats < 2 or repeats > 10:
        return {
            "ok": False,
            "error": (
                "repeats debe estar entre 2 y 10"
            ),
        }

    results = []

    for case_name in DEFAULT_CASES:
        case = get_case_by_name(
            case_name
        )

        for run_number in range(
            1,
            repeats + 1,
        ):
            print(
                (
                    f"Ejecutando {case_name} "
                    f"[{run_number}/{repeats}]..."
                ),
                flush=True,
            )

            result = await run_eval_case(
                case,
                provider,
            )

            results.append({
                "case": case_name,
                "run": run_number,
                "passed": result[
                    "passed"
                ],
                "failed_check_count": (
                    result[
                        "failed_check_count"
                    ]
                ),
                "behavior": result[
                    "behavior"
                ],
                "usage": result[
                    "usage"
                ],
                "checks": result[
                    "checks"
                ],
            })

    grouped = defaultdict(
        list
    )

    for result in results:
        grouped[
            result["case"]
        ].append(
            result
        )

    case_summaries = []

    for case_name in DEFAULT_CASES:
        runs = grouped[
            case_name
        ]

        passed_runs = sum(
            1
            for run in runs
            if run[
                "passed"
            ]
        )

        tool_paths = []

        resource_paths = []

        for run in runs:
            tool_paths.append(
                [
                    call["tool"]
                    for call in run[
                        "behavior"
                    ][
                        "tool_calls"
                    ]
                ]
            )

            resource_paths.append(
                run[
                    "behavior"
                ][
                    "resource_reads"
                ]
            )

        identical_tool_path = all(
            path == tool_paths[0]
            for path in tool_paths
        )

        identical_resource_path = all(
            path == resource_paths[0]
            for path in resource_paths
        )

        case_summaries.append({
            "case": case_name,
            "runs": len(
                runs
            ),
            "passed_runs": (
                passed_runs
            ),
            "pass_rate_percentage": round(
                (
                    passed_runs
                    / len(runs)
                    * 100
                ),
                2,
            ),
            "behavior_stable": (
                identical_tool_path
                and identical_resource_path
            ),
            "tool_paths": (
                tool_paths
            ),
            "resource_paths": (
                resource_paths
            ),
        })

    total_runs = len(
        results
    )

    passed_runs = sum(
        1
        for result in results
        if result[
            "passed"
        ]
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

    total_cost = sum(
        result[
            "usage"
        ][
            "estimated_cost_usd"
        ]
        for result in results
    )

    unstable_cases = [
        summary[
            "case"
        ]
        for summary
        in case_summaries
        if (
            summary[
                "pass_rate_percentage"
            ] < 100
            or not summary[
                "behavior_stable"
            ]
        )
    ]

    return {
        "ok": (
            passed_runs == total_runs
        ),
        "summary": {
            "case_count": len(
                DEFAULT_CASES
            ),
            "repeats_per_case": (
                repeats
            ),
            "total_runs": (
                total_runs
            ),
            "passed_runs": (
                passed_runs
            ),
            "failed_runs": (
                total_runs
                - passed_runs
            ),
            "pass_rate_percentage": round(
                (
                    passed_runs
                    / total_runs
                    * 100
                ),
                2,
            ),
            "unstable_case_count": len(
                unstable_cases
            ),
            "unstable_cases": (
                unstable_cases
            ),
            "total_model_calls": (
                total_model_calls
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
            "average_tokens_per_run": round(
                (
                    total_tokens
                    / total_runs
                ),
                2,
            ),
            "estimated_cost_usd": round(
                total_cost,
                8,
            ),
        },
        "cases": (
            case_summaries
        ),
        "failed_runs": [
            result
            for result in results
            if not result[
                "passed"
            ]
        ],
    }


def build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prueba de estabilidad "
            "del agente UniCore"
        )
    )

    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help=(
            "Número de ejecuciones "
            "por caso"
        ),
    )

    parser.add_argument(
        "--provider",
        default=None,
        help=(
            "Proveedor de IA. "
            "Si se omite usa .env"
        ),
    )

    return parser


async def async_main(
) -> None:
    parser = build_parser()

    args = parser.parse_args()

    result = await run_stability_suite(
        repeats=args.repeats,
        provider=args.provider,
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