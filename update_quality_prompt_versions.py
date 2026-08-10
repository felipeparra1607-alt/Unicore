from __future__ import annotations

import py_compile
import shutil

from pathlib import Path


# ============================================================
# RUTAS
# ============================================================


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
    / "quality_evals_before_prompt_versions.py"
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


if "--prompt-version" in source:
    print(
        "quality_evals.py ya parece "
        "tener soporte de prompt_version."
    )

    print(
        "No se ha modificado nada."
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
# 1. IMPORTAR VERSIONES DEL PROMPT
# ============================================================


old_import = """from src.unicore_agent import (
    UniCoreAgent,
    compact_text,
    extract_json_object,
)
"""


new_import = """from src.unicore_agent import (
    UniCoreAgent,
    compact_text,
    extract_json_object,
)

from src.agent_prompts import (
    DEFAULT_PROMPT_VERSION,
    SUPPORTED_PROMPT_VERSIONS,
)
"""


if old_import not in source:
    raise RuntimeError(
        "No encontré el import esperado "
        "de src.unicore_agent."
    )


source = source.replace(
    old_import,
    new_import,
    1,
)


# ============================================================
# 2. CASOS DETERMINISTAS:
#    AÑADIR prompt_version
# ============================================================


old_quality_case_signature = """async def run_quality_case(
    case: QualityCase,
    provider: str | None,
) -> dict:
"""


new_quality_case_signature = """async def run_quality_case(
    case: QualityCase,
    provider: str | None,
    prompt_version: str,
) -> dict:
"""


if old_quality_case_signature not in source:
    raise RuntimeError(
        "No encontré run_quality_case."
    )


source = source.replace(
    old_quality_case_signature,
    new_quality_case_signature,
    1,
)


old_quality_agent = """    agent = UniCoreAgent(
        provider_name=provider,
        allow_writes=False,
    )
"""


new_quality_agent = """    agent = UniCoreAgent(
        provider_name=provider,
        allow_writes=False,
        prompt_version=(
            prompt_version
        ),
    )
"""


if old_quality_agent not in source:
    raise RuntimeError(
        "No encontré la construcción del agente "
        "en run_quality_case."
    )


source = source.replace(
    old_quality_agent,
    new_quality_agent,
    1,
)


# ============================================================
# 3. SUITE DETERMINISTA:
#    AÑADIR prompt_version
# ============================================================


old_suite_signature = """async def run_deterministic_suite(
    provider: str | None = None,
    selected_case: str | None = None,
) -> dict:
"""


new_suite_signature = """async def run_deterministic_suite(
    provider: str | None = None,
    selected_case: str | None = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> dict:
"""


if old_suite_signature not in source:
    raise RuntimeError(
        "No encontré run_deterministic_suite."
    )


source = source.replace(
    old_suite_signature,
    new_suite_signature,
    1,
)


old_suite_call = """        result = await run_quality_case(
            case,
            provider,
        )
"""


new_suite_call = """        result = await run_quality_case(
            case,
            provider,
            prompt_version,
        )
"""


if old_suite_call not in source:
    raise RuntimeError(
        "No encontré la llamada "
        "a run_quality_case."
    )


source = source.replace(
    old_suite_call,
    new_suite_call,
    1,
)


# ============================================================
# 4. CASO SEMÁNTICO:
#    AÑADIR prompt_version
# ============================================================


old_semantic_signature = """async def run_semantic_rag_case(
    provider_name: str | None,
) -> dict:
"""


new_semantic_signature = """async def run_semantic_rag_case(
    provider_name: str | None,
    prompt_version: str,
) -> dict:
"""


if old_semantic_signature not in source:
    raise RuntimeError(
        "No encontré run_semantic_rag_case."
    )


source = source.replace(
    old_semantic_signature,
    new_semantic_signature,
    1,
)


old_semantic_agent = """    agent = UniCoreAgent(
        provider_name=provider_name,
        allow_writes=False,
    )
"""


new_semantic_agent = """    agent = UniCoreAgent(
        provider_name=provider_name,
        allow_writes=False,
        prompt_version=(
            prompt_version
        ),
    )
"""


if old_semantic_agent not in source:
    raise RuntimeError(
        "No encontré la construcción "
        "del agente semántico."
    )


source = source.replace(
    old_semantic_agent,
    new_semantic_agent,
    1,
)


# ============================================================
# 5. REGISTRAR prompt_version
#    EN EL RESULTADO SEMÁNTICO
# ============================================================


semantic_result_marker = """        "grader_type": (
            "semantic"
        ),
        "request": (
            RAG_SEMANTIC_REQUEST
        ),
        "passed": passed,
"""


semantic_result_replacement = """        "grader_type": (
            "semantic"
        ),
        "prompt_version": (
            prompt_version
        ),
        "request": (
            RAG_SEMANTIC_REQUEST
        ),
        "passed": passed,
"""


if semantic_result_marker not in source:
    raise RuntimeError(
        "No encontré el resultado final "
        "del grader semántico."
    )


source = source.replace(
    semantic_result_marker,
    semantic_result_replacement,
    1,
)


# ============================================================
# 6. AÑADIR ARGUMENTO CLI
# ============================================================


parser_marker = """    parser.add_argument(
        "--list",
        action="store_true",
    )

    return parser
"""


parser_replacement = """    parser.add_argument(
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
"""


if parser_marker not in source:
    raise RuntimeError(
        "No encontré el final "
        "de build_parser."
    )


source = source.replace(
    parser_marker,
    parser_replacement,
    1,
)


# ============================================================
# 7. PASAR prompt_version
#    AL CASO SEMÁNTICO
# ============================================================


old_semantic_cli = """        result = await run_semantic_rag_case(
            provider_name=(
                args.provider
            ),
        )
"""


new_semantic_cli = """        result = await run_semantic_rag_case(
            provider_name=(
                args.provider
            ),
            prompt_version=(
                args.prompt_version
            ),
        )
"""


if old_semantic_cli not in source:
    raise RuntimeError(
        "No encontré la llamada CLI "
        "al grader semántico."
    )


source = source.replace(
    old_semantic_cli,
    new_semantic_cli,
    1,
)


# ============================================================
# 8. PASAR prompt_version
#    A LA SUITE DETERMINISTA
# ============================================================


old_deterministic_cli = """    result = await run_deterministic_suite(
        provider=args.provider,
        selected_case=args.case,
    )
"""


new_deterministic_cli = """    result = await run_deterministic_suite(
        provider=args.provider,
        selected_case=args.case,
        prompt_version=(
            args.prompt_version
        ),
    )
"""


if old_deterministic_cli not in source:
    raise RuntimeError(
        "No encontré la llamada CLI "
        "a run_deterministic_suite."
    )


source = source.replace(
    old_deterministic_cli,
    new_deterministic_cli,
    1,
)


# ============================================================
# GUARDAR
# ============================================================


QUALITY_PATH.write_text(
    source,
    encoding="utf-8",
)


# ============================================================
# COMPILAR
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
        "Restaurando backup..."
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
    "QUALITY EVALS VERSIONADOS"
)

print(
    "============================================"
)

print()
print(
    "Compilación: OK"
)

print()
print(
    "Ahora puedes ejecutar:"
)

print()
print(
    "python -m src.quality_evals "
    "--case rag_workflow_vs_agent_quality "
    "--prompt-version v1"
)

print()
print(
    "python -m src.quality_evals "
    "--case rag_workflow_vs_agent_quality "
    "--prompt-version v2"
)

print()
print(
    "Backup:"
)

print(
    "src/quality_evals_before_prompt_versions.py"
)