from __future__ import annotations

import py_compile
import shutil

from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
)

QUALITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "quality_evals.py"
)

BACKUP_PATH = (
    PROJECT_ROOT
    / "src"
    / "quality_evals_before_grader_retry_v2.py"
)


# ============================================================
# VALIDACIONES
# ============================================================


if not QUALITY_PATH.exists():
    raise FileNotFoundError(
        f"No existe: {QUALITY_PATH}"
    )


source = QUALITY_PATH.read_text(
    encoding="utf-8"
)


if "grader_generation_attempt" in source:
    print(
        "El retry del grader ya está instalado."
    )

    raise SystemExit(
        0
    )


# ============================================================
# BACKUP
# ============================================================


shutil.copy2(
    QUALITY_PATH,
    BACKUP_PATH,
)


print(
    "Backup creado:"
)

print(
    BACKUP_PATH
)


# ============================================================
# LOCALIZAR BLOQUE REAL
# ============================================================


start_marker = """    grader_result = await asyncio.to_thread(
        provider.generate,
        grader_request,
    )
"""


end_marker = """    dimensions = (
"""


start_index = source.find(
    start_marker
)

if start_index == -1:
    raise RuntimeError(
        "No encontré el inicio real "
        "del grader semántico."
    )


end_index = source.find(
    end_marker,
    start_index,
)

if end_index == -1:
    raise RuntimeError(
        "No encontré el final real "
        "del grader semántico."
    )


if end_index <= start_index:
    raise RuntimeError(
        "Los límites encontrados "
        "no son válidos."
    )


print()
print(
    "Bloque del grader localizado correctamente."
)


# ============================================================
# NUEVO BLOQUE ROBUSTO
# ============================================================


new_block = '''    grader_results = []

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
                        + "\\n\\n"
                        + "CORRECCIÓN DE FORMATO:\\n"
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

'''


# ============================================================
# SUSTITUIR SOLO EL BLOQUE
# ============================================================


updated_source = (
    source[
        :start_index
    ]
    + new_block
    + source[
        end_index:
    ]
)


# ============================================================
# ACTUALIZAR grader_usage
# ============================================================


old_usage_block = '''    grader_usage = {
        "model_calls": 1,
        "input_tokens": (
            grader_result.input_tokens
            or 0
        ),
        "output_tokens": (
            grader_result.output_tokens
            or 0
        ),
        "total_tokens": (
            grader_result.total_tokens
            or 0
        ),
        "estimated_cost_usd": (
            grader_result
            .estimated_total_cost_usd
            or 0.0
        ),
    }
'''


new_usage_block = '''    grader_usage = {
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
'''


if (
    old_usage_block
    not in updated_source
):
    raise RuntimeError(
        "No encontré grader_usage "
        "en el archivo actualizado."
    )


updated_source = (
    updated_source.replace(
        old_usage_block,
        new_usage_block,
        1,
    )
)


# ============================================================
# GUARDAR
# ============================================================


QUALITY_PATH.write_text(
    updated_source,
    encoding="utf-8",
)


# ============================================================
# COMPROBAR COMPILACIÓN
# ============================================================


try:
    py_compile.compile(
        str(
            QUALITY_PATH
        ),
        doraise=True,
    )

except Exception:
    print()
    print(
        "ERROR DE COMPILACIÓN."
    )

    print(
        "Restaurando el archivo anterior..."
    )

    shutil.copy2(
        BACKUP_PATH,
        QUALITY_PATH,
    )

    raise


# ============================================================
# RESULTADO
# ============================================================


print()
print(
    "============================================"
)

print(
    "GRADER SEMÁNTICO ACTUALIZADO"
)

print(
    "============================================"
)

print()
print(
    "Retry JSON: ACTIVADO"
)

print(
    "Máximo de intentos del grader: 2"
)

print(
    "Registro de tokens de ambos intentos: ACTIVADO"
)

print(
    "prompt_version también aparece en errores: ACTIVADO"
)

print()
print(
    "Compilación: OK"
)

print()
print(
    "Backup:"
)

print(
    "src/quality_evals_before_grader_retry_v2.py"
)