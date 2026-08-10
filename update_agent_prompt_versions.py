from __future__ import annotations

import py_compile
import re
import shutil

from pathlib import Path


# ============================================================
# RUTAS
# ============================================================


PROJECT_ROOT = Path(__file__).resolve().parent

AGENT_PATH = (
    PROJECT_ROOT
    / "src"
    / "unicore_agent.py"
)

PROMPTS_PATH = (
    PROJECT_ROOT
    / "src"
    / "agent_prompts.py"
)

BACKUP_PATH = (
    PROJECT_ROOT
    / "src"
    / "unicore_agent_before_prompt_versions.py"
)


# ============================================================
# VALIDACIONES INICIALES
# ============================================================


if not AGENT_PATH.exists():
    raise FileNotFoundError(
        f"No existe: {AGENT_PATH}"
    )


if not PROMPTS_PATH.exists():
    raise FileNotFoundError(
        f"No existe: {PROMPTS_PATH}"
    )


source = AGENT_PATH.read_text(
    encoding="utf-8"
)


# ============================================================
# EVITAR EJECUTAR DOS VECES
# ============================================================


if (
    "from src.agent_prompts import ("
    in source
):
    print(
        "unicore_agent.py ya parece estar "
        "versionado."
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
    AGENT_PATH,
    BACKUP_PATH,
)


print(
    "Backup creado:"
)

print(
    BACKUP_PATH
)


# ============================================================
# 1. IMPORTAR SISTEMA DE PROMPTS
# ============================================================


old_import = """from src.capability_router import (
    build_capability_selection,
    filter_resources,
    filter_templates,
    filter_tools,
)
"""


new_import = """from src.capability_router import (
    build_capability_selection,
    filter_resources,
    filter_templates,
    filter_tools,
)

from src.agent_prompts import (
    DEFAULT_PROMPT_VERSION,
    SUPPORTED_PROMPT_VERSIONS,
    build_agent_system_message,
)
"""


if old_import not in source:
    raise RuntimeError(
        "No encontré el bloque esperado "
        "de capability_router."
    )


source = source.replace(
    old_import,
    new_import,
    1,
)


# ============================================================
# 2. ELIMINAR EL PROMPT ANTIGUO EMBEBIDO
# ============================================================


prompt_pattern = re.compile(
    r"""
# ============================================================
# PROMPT\ INTERNO\ DEL\ AGENTE
# ============================================================


def\ build_agent_system_message\(
.*?
(?=def\ get_observation_context_metrics\()
""",
    flags=(
        re.DOTALL
        | re.VERBOSE
    ),
)


replacement_header = """# ============================================================
# PROMPT INTERNO DEL AGENTE
# ============================================================
#
# El contenido del prompt vive ahora en:
#
# src/agent_prompts.py
#
# Esto permite congelar y comparar versiones
# sin mezclar el prompt con el loop del agente.
# ============================================================


"""


source, replacement_count = (
    prompt_pattern.subn(
        replacement_header,
        source,
        count=1,
    )
)


if replacement_count != 1:
    raise RuntimeError(
        "No pude retirar exactamente una "
        "copia del prompt antiguo."
    )


# ============================================================
# 3. AÑADIR prompt_version AL CONSTRUCTOR
# ============================================================


old_constructor = """        maximum_output_tokens: int = 450,
        allow_writes: bool = False,
    ) -> None:
"""


new_constructor = """        maximum_output_tokens: int = 450,
        allow_writes: bool = False,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
    ) -> None:
"""


if old_constructor not in source:
    raise RuntimeError(
        "No encontré la firma esperada "
        "de UniCoreAgent.__init__."
    )


source = source.replace(
    old_constructor,
    new_constructor,
    1,
)


# ============================================================
# 4. VALIDAR Y GUARDAR prompt_version
# ============================================================


old_allow_writes = """        self.allow_writes = (
            allow_writes
        )

        self.usage = AgentUsage()
"""


new_allow_writes = """        self.allow_writes = (
            allow_writes
        )

        if (
            prompt_version
            not in SUPPORTED_PROMPT_VERSIONS
        ):
            raise ValueError(
                "prompt_version no soportada: "
                f"{prompt_version}"
            )

        self.prompt_version = (
            prompt_version
        )

        self.usage = AgentUsage()
"""


if old_allow_writes not in source:
    raise RuntimeError(
        "No encontré el bloque esperado "
        "de allow_writes."
    )


source = source.replace(
    old_allow_writes,
    new_allow_writes,
    1,
)


# ============================================================
# 5. PASAR LA VERSIÓN AL CONSTRUCTOR DEL PROMPT
# ============================================================


old_system_message = """            system_message = (
                build_agent_system_message(
                    tool_catalog=(
                        tool_catalog
                    ),
                    resource_catalog=(
                        resource_catalog
                    ),
                    allow_writes=(
                        self.allow_writes
                    ),
                )
            )
"""


new_system_message = """            system_message = (
                build_agent_system_message(
                    tool_catalog=(
                        tool_catalog
                    ),
                    resource_catalog=(
                        resource_catalog
                    ),
                    allow_writes=(
                        self.allow_writes
                    ),
                    prompt_version=(
                        self.prompt_version
                    ),
                )
            )
"""


if old_system_message not in source:
    raise RuntimeError(
        "No encontré la construcción esperada "
        "del system_message."
    )


source = source.replace(
    old_system_message,
    new_system_message,
    1,
)


# ============================================================
# 6. DEVOLVER prompt_version EN RESULTADOS
# ============================================================
#
# Nos interesa que los evals puedan saber
# exactamente qué versión produjo cada respuesta.
# ============================================================


success_marker = """                        "steps_used": (
                            step_number
                        ),
                        "observations_used": (
"""


success_replacement = """                        "prompt_version": (
                            self.prompt_version
                        ),
                        "steps_used": (
                            step_number
                        ),
                        "observations_used": (
"""


if success_marker not in source:
    raise RuntimeError(
        "No encontré el return exitoso "
        "del agente."
    )


source = source.replace(
    success_marker,
    success_replacement,
    1,
)


# ============================================================
# 7. AÑADIR prompt_version AL CLI
# ============================================================


old_run_cli_signature = """    maximum_output_tokens: int,
    allow_writes: bool,
    show_trace: bool,
) -> None:
"""


new_run_cli_signature = """    maximum_output_tokens: int,
    allow_writes: bool,
    show_trace: bool,
    prompt_version: str,
) -> None:
"""


if old_run_cli_signature not in source:
    raise RuntimeError(
        "No encontré la firma esperada "
        "de run_cli."
    )


source = source.replace(
    old_run_cli_signature,
    new_run_cli_signature,
    1,
)


# ============================================================
# 8. PASAR prompt_version AL AGENTE DESDE EL CLI
# ============================================================


old_cli_agent = """        maximum_output_tokens=(
            maximum_output_tokens
        ),
        allow_writes=allow_writes,
    )
"""


new_cli_agent = """        maximum_output_tokens=(
            maximum_output_tokens
        ),
        allow_writes=allow_writes,
        prompt_version=(
            prompt_version
        ),
    )
"""


if old_cli_agent not in source:
    raise RuntimeError(
        "No encontré la creación del agente "
        "dentro de run_cli."
    )


source = source.replace(
    old_cli_agent,
    new_cli_agent,
    1,
)


# ============================================================
# 9. AÑADIR --prompt-version AL PARSER
# ============================================================


parser_marker = """    parser.add_argument(
        "--show-trace",
        action="store_true",
        help=(
            "Muestra las decisiones internas "
            "estructuradas del agente"
        ),
    )

    return parser
"""


parser_replacement = """    parser.add_argument(
        "--show-trace",
        action="store_true",
        help=(
            "Muestra las decisiones internas "
            "estructuradas del agente"
        ),
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
            "Versión del prompt interno "
            "del agente"
        ),
    )

    return parser
"""


if parser_marker not in source:
    raise RuntimeError(
        "No encontré el final esperado "
        "de build_parser."
    )


source = source.replace(
    parser_marker,
    parser_replacement,
    1,
)


# ============================================================
# 10. PASAR EL ARGUMENTO DESDE main()
# ============================================================


old_main_call = """            show_trace=(
                args.show_trace
            ),
        )
"""


new_main_call = """            show_trace=(
                args.show_trace
            ),
            prompt_version=(
                args.prompt_version
            ),
        )
"""


if old_main_call not in source:
    raise RuntimeError(
        "No encontré la llamada esperada "
        "a run_cli desde main."
    )


source = source.replace(
    old_main_call,
    new_main_call,
    1,
)


# ============================================================
# GUARDAR
# ============================================================


AGENT_PATH.write_text(
    source,
    encoding="utf-8",
)


# ============================================================
# COMPILAR AMBOS ARCHIVOS
# ============================================================


try:
    py_compile.compile(
        str(
            PROMPTS_PATH
        ),
        doraise=True,
    )

    py_compile.compile(
        str(
            AGENT_PATH
        ),
        doraise=True,
    )

except Exception:
    print()
    print(
        "ERROR DE COMPILACIÓN."
    )

    print(
        "Restaurando el backup..."
    )

    shutil.copy2(
        BACKUP_PATH,
        AGENT_PATH,
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
    "VERSIONADO DEL PROMPT COMPLETADO"
)

print(
    "============================================"
)

print()
print(
    "Archivos válidos:"
)

print(
    "  src/agent_prompts.py"
)

print(
    "  src/unicore_agent.py"
)

print()
print(
    "Versiones disponibles:"
)

print(
    "  v1 = baseline de Fase 8"
)

print(
    "  v2 = grounding mejorado"
)

print()
print(
    "Compilación: OK"
)

print()
print(
    "Backup conservado en:"
)

print(
    "  src/unicore_agent_before_prompt_versions.py"
)