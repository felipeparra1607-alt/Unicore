from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


# ============================================================
# TIPOS DE HANDOFF
# ============================================================


HANDOFF_KIND_LONG_ANALYSIS = (
    "long_analysis"
)

HANDOFF_KIND_RESEARCH = (
    "research"
)

HANDOFF_KIND_ARTIFACT = (
    "artifact"
)


SUPPORTED_HANDOFF_KINDS = {
    HANDOFF_KIND_LONG_ANALYSIS,
    HANDOFF_KIND_RESEARCH,
    HANDOFF_KIND_ARTIFACT,
}


# ============================================================
# ESTADOS
# ============================================================


HANDOFF_STATUS_REQUESTED = (
    "requested"
)

HANDOFF_STATUS_REJECTED = (
    "rejected"
)


# ============================================================
# MODELO
# ============================================================


@dataclass(frozen=True)
class HandoffRequest:
    """
    Contrato interno que representa trabajo que el
    agente interactivo decide delegar.

    Todavía NO crea un Job.

    La siguiente fase convertirá este objeto en
    trabajo persistente/asíncrono.
    """

    kind: str

    objective: str

    context_summary: str

    expected_output: str

    source_uris: tuple[str, ...] = ()

    requires_write: bool = False


# ============================================================
# NORMALIZACIÓN
# ============================================================


def normalize_required_text(
    value: Any,
    field_name: str,
    maximum_characters: int,
) -> str:
    text = str(
        value
        or ""
    ).strip()

    if not text:
        raise ValueError(
            f"{field_name} no puede estar vacío"
        )

    if (
        len(text)
        > maximum_characters
    ):
        raise ValueError(
            f"{field_name} supera "
            f"{maximum_characters} caracteres"
        )

    return text


def normalize_source_uris(
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
            "source_uris debe ser una colección"
        )

    result: list[str] = []

    for value in values:
        uri = str(
            value
            or ""
        ).strip()

        if not uri:
            continue

        if (
            uri not in result
        ):
            result.append(
                uri
            )

    if (
        len(result)
        > 20
    ):
        raise ValueError(
            "source_uris no puede contener "
            "más de 20 elementos"
        )

    return tuple(
        result
    )


# ============================================================
# CONSTRUCTOR VALIDADO
# ============================================================


def build_handoff_request(
    kind: str,
    objective: str,
    context_summary: str,
    expected_output: str,
    source_uris: Any = None,
    requires_write: bool = False,
) -> HandoffRequest:
    """
    Construye un HandoffRequest válido.

    No ejecuta ningún modelo.
    No toca la base de datos.
    No crea Jobs.
    """

    clean_kind = str(
        kind
        or ""
    ).strip().casefold()

    if (
        clean_kind
        not in SUPPORTED_HANDOFF_KINDS
    ):
        raise ValueError(
            "Tipo de handoff no soportado: "
            f"{clean_kind}"
        )

    clean_objective = (
        normalize_required_text(
            objective,
            "objective",
            2000,
        )
    )

    clean_context_summary = (
        normalize_required_text(
            context_summary,
            "context_summary",
            4000,
        )
    )

    clean_expected_output = (
        normalize_required_text(
            expected_output,
            "expected_output",
            1000,
        )
    )

    clean_source_uris = (
        normalize_source_uris(
            source_uris
        )
    )

    return HandoffRequest(
        kind=clean_kind,
        objective=clean_objective,
        context_summary=(
            clean_context_summary
        ),
        expected_output=(
            clean_expected_output
        ),
        source_uris=(
            clean_source_uris
        ),
        requires_write=bool(
            requires_write
        ),
    )


# ============================================================
# SERIALIZACIÓN
# ============================================================


def handoff_to_dict(
    handoff: HandoffRequest,
) -> dict:
    result = asdict(
        handoff
    )

    result[
        "source_uris"
    ] = list(
        handoff.source_uris
    )

    result[
        "status"
    ] = (
        HANDOFF_STATUS_REQUESTED
    )

    return result