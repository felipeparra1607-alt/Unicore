from __future__ import annotations

import argparse
import json

from src.job_worker import (
    JobWorker,
    WORKER_MODE_EXECUTE,
    WORKER_MODE_LIFECYCLE_ONLY,
)


def build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecutor local de Jobs de UniCore"
        )
    )

    parser.add_argument(
        "job_id",
        help=(
            "ID del Job que se quiere ejecutar"
        ),
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Ejecuta realmente el Job con IA. "
            "Sin esta opción solo prueba el lifecycle."
        ),
    )

    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help=(
            "Permite Jobs que requieren escritura."
        ),
    )

    parser.add_argument(
        "--provider",
        default=None,
    )

    parser.add_argument(
        "--maximum-steps",
        type=int,
        default=10,
    )

    return parser


def main(
) -> None:
    parser = build_parser()

    args = parser.parse_args()

    mode = (
        WORKER_MODE_EXECUTE
        if args.execute
        else WORKER_MODE_LIFECYCLE_ONLY
    )

    worker = JobWorker(
        allow_writes=(
            args.allow_writes
        ),
        mode=mode,
        provider_name=(
            args.provider
        ),
        worker_prompt_version="v2",
        maximum_steps=(
            args.maximum_steps
        ),
    )

    result = worker.run(
        args.job_id
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()