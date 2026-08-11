from __future__ import annotations

import uuid

from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeContext:
    conversation_id: str
    job_id: str | None = None
    study_session_id: int | None = None
    allow_writes: bool = False
    allowed_paths: tuple[str, ...] = ()


def create_conversation_id() -> str:
    return "conv_" + uuid.uuid4().hex


def normalize_identifier(
    value: Any,
) -> str | None:
    text = str(value or "").strip()

    if not text:
        return None

    return text


def normalize_study_session_id(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            "study_session_id debe ser un entero"
        )

    if parsed <= 0:
        raise ValueError(
            "study_session_id debe ser mayor que 0"
        )

    return parsed


def normalize_allowed_paths(
    values: Any,
) -> tuple[str, ...]:
    if values is None:
        return ()

    if not isinstance(
        values,
        (
            list,
            tuple,
            set,
        ),
    ):
        raise ValueError(
            "allowed_paths debe ser una colección"
        )

    result: list[str] = []

    for value in values:
        raw_path = str(
            value or ""
        ).strip()

        if not raw_path:
            continue

        normalized = str(
            Path(
                raw_path
            ).expanduser().resolve()
        )

        if normalized not in result:
            result.append(normalized)

    return tuple(result)


def build_runtime_context(
    *,
    conversation_id: str | None = None,
    job_id: str | None = None,
    study_session_id: int | None = None,
    allow_writes: bool = False,
    allowed_paths: Any = None,
) -> RuntimeContext:
    clean_conversation_id = (
        normalize_identifier(
            conversation_id
        )
        or create_conversation_id()
    )

    clean_job_id = normalize_identifier(
        job_id
    )

    clean_study_session_id = (
        normalize_study_session_id(
            study_session_id
        )
    )

    clean_allowed_paths = (
        normalize_allowed_paths(
            allowed_paths
        )
    )

    return RuntimeContext(
        conversation_id=clean_conversation_id,
        job_id=clean_job_id,
        study_session_id=clean_study_session_id,
        allow_writes=bool(
            allow_writes
        ),
        allowed_paths=clean_allowed_paths,
    )


def derive_runtime_context(
    context: RuntimeContext,
    *,
    job_id: str | None = None,
    study_session_id: int | None = None,
    allow_writes: bool | None = None,
    allowed_paths: Any = None,
) -> RuntimeContext:
    return build_runtime_context(
        conversation_id=(
            context.conversation_id
        ),
        job_id=(
            job_id
            if job_id is not None
            else context.job_id
        ),
        study_session_id=(
            study_session_id
            if study_session_id is not None
            else context.study_session_id
        ),
        allow_writes=(
            context.allow_writes
            if allow_writes is None
            else allow_writes
        ),
        allowed_paths=(
            context.allowed_paths
            if allowed_paths is None
            else allowed_paths
        ),
    )


def can_write(
    context: RuntimeContext,
) -> bool:
    return bool(
        context.allow_writes
    )


def is_path_allowed(
    context: RuntimeContext,
    path: str | Path,
) -> bool:
    if not context.allowed_paths:
        return False

    candidate = (
        Path(path)
        .expanduser()
        .resolve()
    )

    for allowed_path in (
        context.allowed_paths
    ):
        allowed = (
            Path(
                allowed_path
            )
            .expanduser()
            .resolve()
        )

        try:
            candidate.relative_to(
                allowed
            )
            return True
        except ValueError:
            continue

    return False


def runtime_context_to_dict(
    context: RuntimeContext,
) -> dict:
    result = asdict(
        context
    )

    result["allowed_paths"] = list(
        context.allowed_paths
    )

    return result