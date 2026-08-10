from __future__ import annotations

import py_compile
import shutil

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parent
)

SRC = (
    ROOT
    / "src"
)

SERVER_PATH = (
    SRC
    / "server.py"
)

JOBS_MCP_PATH = (
    SRC
    / "jobs_mcp.py"
)

AGENT_PATH = (
    SRC
    / "unicore_agent.py"
)

ROUTER_PATH = (
    SRC
    / "capability_router.py"
)

CATALOG_PATH = (
    SRC
    / "mcp_catalog.py"
)


BACKUPS = {
    SERVER_PATH: (
        SRC
        / "server_before_jobs_mcp.py"
    ),
    JOBS_MCP_PATH: (
        SRC
        / "jobs_mcp_before_registration.py"
    ),
    AGENT_PATH: (
        SRC
        / "unicore_agent_before_jobs_mcp.py"
    ),
    ROUTER_PATH: (
        SRC
        / "capability_router_before_jobs_mcp.py"
    ),
}


# ============================================================
# VALIDACIONES
# ============================================================


for path in (
    SERVER_PATH,
    JOBS_MCP_PATH,
    AGENT_PATH,
    ROUTER_PATH,
    CATALOG_PATH,
):
    if not path.exists():
        raise FileNotFoundError(
            f"No existe: {path}"
        )


server_source = (
    SERVER_PATH.read_text(
        encoding="utf-8"
    )
)

agent_source = (
    AGENT_PATH.read_text(
        encoding="utf-8"
    )
)

router_source = (
    ROUTER_PATH.read_text(
        encoding="utf-8"
    )
)

catalog_source = (
    CATALOG_PATH.read_text(
        encoding="utf-8"
    )
)


if (
    "register_jobs_mcp"
    in server_source
):
    print(
        "Jobs MCP ya parece instalado."
    )

    raise SystemExit(
        0
    )


# ============================================================
# BACKUPS
# ============================================================


for original, backup in (
    BACKUPS.items()
):
    shutil.copy2(
        original,
        backup,
    )


print(
    "Backups creados."
)


# ============================================================
# 1. REEMPLAZAR jobs_mcp.py
# ============================================================
#
# IMPORTANTE:
#
# unicore://jobs devuelve RESÚMENES compactos.
#
# No incluimos el resultado completo de todos los Jobs,
# porque un artifact puede contener miles de caracteres.
#
# unicore://jobs/{job_id} sí devuelve el Job completo.
# ============================================================


jobs_mcp_source = r'''from __future__ import annotations

import json

from src.job_manager import (
    JobManager,
)

from src.jobs import (
    Job,
    job_to_dict,
)


# ============================================================
# SERIALIZACIÓN
# ============================================================


def _json(
    value,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


# ============================================================
# COMPACTACIÓN
# ============================================================


def job_summary(
    job: Job,
) -> dict:
    """
    Representación compacta para listados.

    No incluye:
    - context_summary completo;
    - result completo.

    Así evitamos introducir artefactos largos
    en el contexto del agente solo por listar Jobs.
    """

    has_result = bool(
        str(
            job.result
            or ""
        ).strip()
    )

    return {
        "job_id": (
            job.job_id
        ),
        "status": (
            job.status
        ),
        "kind": (
            job.kind
        ),
        "objective": (
            job.objective
        ),
        "expected_output": (
            job.expected_output
        ),
        "requires_write": (
            job.requires_write
        ),
        "created_at": (
            job.created_at
        ),
        "started_at": (
            job.started_at
        ),
        "completed_at": (
            job.completed_at
        ),
        "has_result": (
            has_result
        ),
        "error": (
            job.error
        ),
    }


# ============================================================
# PAYLOADS
# ============================================================


def get_jobs_resource_payload(
    *,
    status: str | None = None,
    limit: int = 20,
) -> dict:
    manager = (
        JobManager()
    )

    jobs = manager.list(
        status=status,
        limit=limit,
    )

    return {
        "ok": True,
        "count": len(
            jobs
        ),
        "jobs": [
            job_summary(
                job
            )
            for job in jobs
        ],
    }


def get_job_resource_payload(
    job_id: str,
) -> dict:
    manager = (
        JobManager()
    )

    job = manager.get(
        job_id
    )

    if job is None:
        return {
            "ok": False,
            "error": (
                "Job inexistente"
            ),
            "job_id": (
                job_id
            ),
        }

    return {
        "ok": True,
        "job": (
            job_to_dict(
                job
            )
        ),
    }


def get_job_status_payload(
    job_id: str,
) -> dict:
    manager = (
        JobManager()
    )

    job = manager.get(
        job_id
    )

    if job is None:
        return {
            "ok": False,
            "error": (
                "Job inexistente"
            ),
            "job_id": (
                job_id
            ),
        }

    return {
        "ok": True,
        "job": (
            job_summary(
                job
            )
        ),
    }


# ============================================================
# REGISTRO MCP
# ============================================================


def register_jobs_mcp(
    mcp,
) -> None:
    """
    Expone Jobs mediante MCP.

    Tools:
    - get_job_status
    - list_jobs

    Resources:
    - unicore://jobs
    - unicore://jobs/{job_id}
    """

    # --------------------------------------------------------
    # TOOLS
    # --------------------------------------------------------

    @mcp.tool()
    def get_job_status(
        job_id: str,
    ) -> dict:
        """
        Consulta el estado compacto de un Job de UniCore.

        No devuelve el resultado largo del Job.
        Para recuperar el Job completo utiliza
        unicore://jobs/{job_id}.
        """

        return get_job_status_payload(
            job_id
        )


    @mcp.tool()
    def list_jobs(
        status: str | None = None,
        limit: int = 20,
    ) -> dict:
        """
        Lista Jobs de UniCore de forma compacta.

        status puede ser:
        pending, running, completed o failed.
        """

        try:
            return (
                get_jobs_resource_payload(
                    status=status,
                    limit=limit,
                )
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    str(
                        error
                    )
                ),
            }


    # --------------------------------------------------------
    # DIRECT RESOURCE
    # --------------------------------------------------------

    @mcp.resource(
        "unicore://jobs"
    )
    def jobs_resource(
    ) -> str:
        """
        Lista compacta de los Jobs más recientes.
        """

        return _json(
            get_jobs_resource_payload(
                limit=20
            )
        )


    # --------------------------------------------------------
    # RESOURCE TEMPLATE
    # --------------------------------------------------------

    @mcp.resource(
        "unicore://jobs/{job_id}"
    )
    def job_resource(
        job_id: str,
    ) -> str:
        """
        Devuelve un Job concreto, incluido su resultado
        persistido cuando haya terminado.
        """

        return _json(
            get_job_resource_payload(
                job_id
            )
        )
'''


JOBS_MCP_PATH.write_text(
    jobs_mcp_source,
    encoding="utf-8",
)


# ============================================================
# 2. SERVER.PY
# ============================================================


server_import_marker = '''from src.decision_engine import (
    register_decision_engine,
)
'''


server_import_replacement = '''from src.decision_engine import (
    register_decision_engine,
)
from src.jobs_mcp import (
    register_jobs_mcp,
)
'''


if (
    server_import_marker
    not in server_source
):
    raise RuntimeError(
        "No encontré el import "
        "de decision_engine en server.py"
    )


server_source = (
    server_source.replace(
        server_import_marker,
        server_import_replacement,
        1,
    )
)


server_register_marker = (
    "register_decision_engine(mcp)\n"
)


server_register_replacement = (
    "register_decision_engine(mcp)\n"
    "register_jobs_mcp(mcp)\n"
)


if (
    server_register_marker
    not in server_source
):
    raise RuntimeError(
        "No encontré register_decision_engine(mcp)"
    )


server_source = (
    server_source.replace(
        server_register_marker,
        server_register_replacement,
        1,
    )
)


# Debe seguir existiendo exactamente una aplicación
# del catálogo público y debe estar después de registrar
# Jobs.
if (
    server_source.count(
        "apply_public_tool_catalog(mcp)"
    )
    != 1
):
    raise RuntimeError(
        "apply_public_tool_catalog(mcp) "
        "no aparece exactamente una vez"
    )


if (
    server_source.find(
        "register_jobs_mcp(mcp)"
    )
    > server_source.find(
        "apply_public_tool_catalog(mcp)"
    )
):
    raise RuntimeError(
        "Jobs MCP quedó registrado después "
        "del catálogo público"
    )


SERVER_PATH.write_text(
    server_source,
    encoding="utf-8",
)


# ============================================================
# 3. AGENT_READ_TOOLS
# ============================================================


agent_start_marker = (
    "AGENT_READ_TOOLS = {\n"
)

agent_end_marker = (
    "\n\n\nAGENT_WRITE_TOOLS = {"
)


agent_start = (
    agent_source.find(
        agent_start_marker
    )
)

agent_end = (
    agent_source.find(
        agent_end_marker,
        agent_start,
    )
)


if (
    agent_start == -1
    or agent_end == -1
):
    raise RuntimeError(
        "No encontré AGENT_READ_TOOLS"
    )


new_agent_read_tools = '''AGENT_READ_TOOLS = {
    "recommend_next_actions",
    "answer_with_rag",
    "hybrid_search",
    "get_rag_source",
    "get_quiz_attempt",
    "get_review_plan",
    "simulate_assessment_grade",
    "get_job_status",
    "list_jobs",
    "health_check",
}'''


agent_source = (
    agent_source[
        :agent_start
    ]
    + new_agent_read_tools
    + agent_source[
        agent_end:
    ]
)


AGENT_PATH.write_text(
    agent_source,
    encoding="utf-8",
)


# ============================================================
# 4. CAPABILITY ROUTER — PERFIL JOBS
# ============================================================


profile_marker = '''    "tasks": CapabilitySelection(
        profile="tasks",
'''


jobs_profile = '''    "jobs": CapabilitySelection(
        profile="jobs",
        tool_names=frozenset({
            "get_job_status",
            "list_jobs",
        }),
        direct_resource_uris=frozenset({
            "unicore://jobs",
        }),
        template_fragments=frozenset({
            "/jobs",
        }),
    ),

'''


if (
    profile_marker
    not in router_source
):
    raise RuntimeError(
        "No encontré el perfil tasks"
    )


router_source = (
    router_source.replace(
        profile_marker,
        jobs_profile
        + profile_marker,
        1,
    )
)


# ============================================================
# 5. CAPABILITY ROUTER — DETECCIÓN JOBS
# ============================================================


tasks_section_marker = '''    # --------------------------------------------------------
    # TAREAS
    # --------------------------------------------------------
'''


jobs_detection = '''    # --------------------------------------------------------
    # JOBS / TRABAJOS DELEGADOS
    # --------------------------------------------------------

    job_expressions = (
        "job",
        "jobs",
        "trabajo de unicore",
        "trabajos de unicore",
        "trabajo delegado",
        "trabajos delegados",
        "resultado del trabajo",
        "resultado del analisis",
        "resultado del informe",
        "analisis que pedi",
        "informe que pedi",
        "trabajo que pedi",
        "como va mi analisis",
        "como va el analisis",
        "como va mi trabajo",
        "ya termino el analisis",
        "ya termino mi analisis",
        "ya termino el trabajo",
        "estado del analisis",
        "estado del trabajo",
    )

    if contains_any(
        text,
        job_expressions,
    ):
        profiles.add(
            "jobs"
        )

'''


if (
    tasks_section_marker
    not in router_source
):
    raise RuntimeError(
        "No encontré la sección TAREAS"
    )


router_source = (
    router_source.replace(
        tasks_section_marker,
        jobs_detection
        + tasks_section_marker,
        1,
    )
)


# ============================================================
# 6. DESAMBIGUAR JOBS VS ACADEMIC TASKS
# ============================================================
#
# "resultado del trabajo que pedí"
#
# contiene "trabajo" y sin esto activaría:
#
# jobs + tasks
#
# Si la expresión es explícitamente de Jobs,
# eliminamos tasks.
# ============================================================


disambiguation_marker = '''    # --------------------------------------------------------
    # DESAMBIGUACIÓN
    # --------------------------------------------------------
'''


jobs_disambiguation = '''    # --------------------------------------------------------
    # JOBS VS TAREAS ACADÉMICAS
    # --------------------------------------------------------

    if (
        "jobs" in profiles
        and "tasks" in profiles
        and contains_any(
            text,
            job_expressions,
        )
    ):
        profiles.discard(
            "tasks"
        )

'''


if (
    disambiguation_marker
    not in router_source
):
    raise RuntimeError(
        "No encontré DESAMBIGUACIÓN"
    )


router_source = (
    router_source.replace(
        disambiguation_marker,
        jobs_disambiguation
        + disambiguation_marker,
        1,
    )
)


ROUTER_PATH.write_text(
    router_source,
    encoding="utf-8",
)


# ============================================================
# 7. VALIDAR CATÁLOGO PÚBLICO
# ============================================================


for job_tool in (
    '"get_job_status"',
    '"list_jobs"',
):
    if (
        job_tool
        in catalog_source
    ):
        raise RuntimeError(
            "Una Tool de Jobs aparece en "
            "mcp_catalog.py. Revisa si quedó "
            "oculta accidentalmente: "
            + job_tool
        )


# ============================================================
# 8. COMPILAR
# ============================================================


paths_to_compile = (
    JOBS_MCP_PATH,
    SERVER_PATH,
    AGENT_PATH,
    ROUTER_PATH,
)


try:
    for path in paths_to_compile:
        py_compile.compile(
            str(
                path
            ),
            doraise=True,
        )

except Exception:
    print()
    print(
        "ERROR."
    )

    print(
        "Restaurando backups..."
    )

    for original, backup in (
        BACKUPS.items()
    ):
        shutil.copy2(
            backup,
            original,
        )

    raise


print()
print(
    "============================================"
)

print(
    "JOBS MCP INSTALADO"
)

print(
    "============================================"
)

print()
print(
    "Tools:"
)

print(
    "  get_job_status"
)

print(
    "  list_jobs"
)

print()
print(
    "Resources:"
)

print(
    "  unicore://jobs"
)

print(
    "  unicore://jobs/{job_id}"
)

print()
print(
    "Capability profile:"
)

print(
    "  jobs"
)

print()
print(
    "Compilación: OK"
)

print()
print(
    "apply_public_tool_catalog sigue "
    "después de Jobs: OK"
)