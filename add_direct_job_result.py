from __future__ import annotations

import py_compile
import shutil

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parent
)

AGENT_PATH = (
    ROOT
    / "src"
    / "unicore_agent.py"
)

BACKUP_PATH = (
    ROOT
    / "src"
    / "unicore_agent_before_direct_job_result.py"
)


if not AGENT_PATH.exists():
    raise FileNotFoundError(
        AGENT_PATH
    )


source = AGENT_PATH.read_text(
    encoding="utf-8"
)


if "extract_job_result_answer" in source:
    print(
        "Direct Job Result ya parece instalado."
    )
    raise SystemExit(0)


shutil.copy2(
    AGENT_PATH,
    BACKUP_PATH,
)


# ============================================================
# 1. HELPER DE EXTRACCIÓN
# ============================================================


helper_marker = '''def compact_tool_catalog(
    tools: list[dict],
) -> list[dict]:
'''


helper_code = r'''def extract_job_result_answer(
    value: Any,
) -> str | None:
    """
    Intenta extraer el answer persistido de un Job
    recuperado mediante MCP.

    Soporta:
    - dicts;
    - listas;
    - JSON serializado como string;
    - wrappers producidos por el cliente MCP.

    No inventa ni resume el resultado.
    Devuelve exactamente el answer persistido
    cuando puede localizarlo.
    """

    def walk(
        current: Any,
        depth: int = 0,
    ) -> str | None:
        if depth > 8:
            return None

        if isinstance(
            current,
            dict,
        ):
            # Caso directo:
            #
            # {
            #   "worker_mode": "...",
            #   "answer": "..."
            # }
            answer = current.get(
                "answer"
            )

            if isinstance(
                answer,
                str,
            ):
                clean_answer = (
                    answer.strip()
                )

                if clean_answer:
                    return clean_answer

            # Caso Job:
            #
            # {
            #   "job": {
            #       "result": ...
            #   }
            # }
            for key in (
                "result",
                "job",
                "content",
                "text",
            ):
                if key in current:
                    found = walk(
                        current[
                            key
                        ],
                        depth + 1,
                    )

                    if found:
                        return found

            # Fallback:
            # inspeccionar valores anidados.
            for nested_value in (
                current.values()
            ):
                found = walk(
                    nested_value,
                    depth + 1,
                )

                if found:
                    return found

            return None

        if isinstance(
            current,
            (
                list,
                tuple,
            ),
        ):
            for item in current:
                found = walk(
                    item,
                    depth + 1,
                )

                if found:
                    return found

            return None

        if isinstance(
            current,
            str,
        ):
            clean = (
                current.strip()
            )

            if not clean:
                return None

            # Primero intentamos interpretar
            # el string completo como JSON.
            try:
                parsed = json.loads(
                    clean
                )

            except (
                json.JSONDecodeError,
                TypeError,
            ):
                parsed = None

            if (
                parsed is not None
                and parsed is not current
            ):
                found = walk(
                    parsed,
                    depth + 1,
                )

                if found:
                    return found

            # Algunos wrappers MCP pueden contener
            # texto alrededor de un JSON.
            start = clean.find(
                "{"
            )

            end = clean.rfind(
                "}"
            )

            if (
                start != -1
                and end > start
            ):
                candidate = clean[
                    start : end + 1
                ]

                try:
                    parsed_candidate = (
                        json.loads(
                            candidate
                        )
                    )

                except json.JSONDecodeError:
                    parsed_candidate = None

                if (
                    parsed_candidate
                    is not None
                ):
                    found = walk(
                        parsed_candidate,
                        depth + 1,
                    )

                    if found:
                        return found

            return None

        return None

    return walk(
        value
    )


def user_requests_explicit_job_result(
    user_request: str,
    uri: str,
) -> bool:
    """
    Fast path únicamente para una petición explícita
    del resultado de un Job concreto.

    No se usa para:
    - listar Jobs;
    - preguntar estados;
    - consultas ambiguas.
    """

    clean_request = (
        user_request
        .strip()
        .casefold()
    )

    clean_uri = (
        uri
        .strip()
        .casefold()
    )

    if not clean_uri.startswith(
        "unicore://jobs/job_"
    ):
        return False

    result_expressions = (
        "resultado",
        "enséñame",
        "ensename",
        "muéstrame",
        "muestrame",
        "dame",
        "ver el job",
        "ver job",
    )

    return any(
        expression
        in clean_request
        for expression
        in result_expressions
    )


'''


if helper_marker not in source:
    raise RuntimeError(
        "No encontré compact_tool_catalog"
    )


source = source.replace(
    helper_marker,
    helper_code
    + helper_marker,
    1,
)


# ============================================================
# 2. FAST PATH EN RESOURCE
# ============================================================


resource_marker = '''                        self.usage.mcp_resource_reads += 1

                        observation = {
                            "type": "resource",
                            "uri": uri,
                            "result": (
                                compact_text(
                                    result
                                )
                            ),
                        }

                        observations.append(
                            observation
                        )

                        trace_entry[
                            "status"
                        ] = "resource_read"

                        trace_entry[
                            "uri"
                        ] = uri
'''


resource_replacement = '''                        self.usage.mcp_resource_reads += 1

                        observation = {
                            "type": "resource",
                            "uri": uri,
                            "result": (
                                compact_text(
                                    result
                                )
                            ),
                        }

                        observations.append(
                            observation
                        )

                        trace_entry[
                            "status"
                        ] = "resource_read"

                        trace_entry[
                            "uri"
                        ] = uri

                        # ====================================
                        # DIRECT JOB RESULT
                        # ====================================
                        #
                        # Si el usuario ha pedido
                        # explícitamente el resultado de un
                        # Job concreto, no necesitamos otra
                        # llamada al modelo para envolver un
                        # resultado largo dentro de:
                        #
                        # {"action":"finish","answer":"..."}
                        #
                        # Extraemos directamente el answer
                        # persistido que acaba de llegar desde
                        # MCP.
                        # ====================================

                        if (
                            user_requests_explicit_job_result(
                                clean_request,
                                uri,
                            )
                        ):
                            job_answer = (
                                extract_job_result_answer(
                                    result
                                )
                            )

                            if job_answer:
                                trace_entry[
                                    "status"
                                ] = (
                                    "job_result_returned_directly"
                                )

                                trace.append(
                                    trace_entry
                                )

                                return {
                                    "ok": True,
                                    "answer": (
                                        job_answer
                                    ),
                                    "capability_selection": {
                                        "profiles": (
                                            capability_selection[
                                                "profiles"
                                            ]
                                        ),
                                        "broad_fallback": (
                                            capability_selection[
                                                "broad_fallback"
                                            ]
                                        ),
                                        "tool_count": len(
                                            tool_catalog
                                        ),
                                        "resource_count": len(
                                            resource_catalog[
                                                "direct"
                                            ]
                                        ),
                                        "template_count": len(
                                            resource_catalog[
                                                "templates"
                                            ]
                                        ),
                                    },
                                    "context_metrics": (
                                        context_metrics
                                    ),
                                    "prompt_version": (
                                        self.prompt_version
                                    ),
                                    "steps_used": (
                                        step_number
                                    ),
                                    "observations_used": (
                                        len(
                                            observations
                                        )
                                    ),
                                    "trace": trace,
                                    "usage": (
                                        self.usage.to_dict()
                                    ),
                                    "policy": {
                                        "writes_allowed": (
                                            self.allow_writes
                                        ),
                                        "maximum_steps": (
                                            self.maximum_steps
                                        ),
                                    },
                                    "direct_return": (
                                        "job_result"
                                    ),
                                }
'''


if resource_marker not in source:
    raise RuntimeError(
        "No encontré el bloque actual "
        "de lectura de Resource"
    )


source = source.replace(
    resource_marker,
    resource_replacement,
    1,
)


# ============================================================
# GUARDAR + COMPILAR
# ============================================================


AGENT_PATH.write_text(
    source,
    encoding="utf-8",
)


try:
    py_compile.compile(
        str(
            AGENT_PATH
        ),
        doraise=True,
    )

except Exception:
    shutil.copy2(
        BACKUP_PATH,
        AGENT_PATH,
    )

    raise


print()
print(
    "============================================"
)

print(
    "DIRECT JOB RESULT INSTALADO"
)

print(
    "============================================"
)

print()
print(
    "Compilación: OK"
)

print(
    "Backup:"
)

print(
    "src/unicore_agent_before_direct_job_result.py"
)