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
    / "unicore_agent_before_jobs.py"
)


if not AGENT_PATH.exists():
    raise FileNotFoundError(
        f"No existe: {AGENT_PATH}"
    )


source = AGENT_PATH.read_text(
    encoding="utf-8"
)


if "JobManager" in source:
    print(
        "La integración Handoff → Job "
        "ya parece instalada."
    )

    raise SystemExit(
        0
    )


shutil.copy2(
    AGENT_PATH,
    BACKUP_PATH,
)


# ============================================================
# IMPORT
# ============================================================


import_marker = """from src.handoff import (
    HANDOFF_KIND_ARTIFACT,
    HANDOFF_KIND_LONG_ANALYSIS,
    HANDOFF_KIND_RESEARCH,
    build_handoff_request,
    handoff_to_dict,
)
"""


import_replacement = """from src.handoff import (
    HANDOFF_KIND_ARTIFACT,
    HANDOFF_KIND_LONG_ANALYSIS,
    HANDOFF_KIND_RESEARCH,
    build_handoff_request,
    handoff_to_dict,
)

from src.job_manager import (
    JobManager,
)

from src.jobs import (
    job_to_dict,
)
"""


if import_marker not in source:
    raise RuntimeError(
        "No encontré el import actual "
        "de handoff."
    )


source = source.replace(
    import_marker,
    import_replacement,
    1,
)


# ============================================================
# CREAR JOB DESPUÉS DEL HANDOFF VALIDADO
# ============================================================


marker = """                    serialized_handoff = (
                        handoff_to_dict(
                            handoff_request
                        )
                    )

                    trace_entry[
                        "status"
                    ] = (
                        "handoff_requested"
                    )
"""


replacement = """                    serialized_handoff = (
                        handoff_to_dict(
                            handoff_request
                        )
                    )

                    job_manager = (
                        JobManager()
                    )

                    job = (
                        job_manager
                        .create_from_handoff(
                            handoff_request
                        )
                    )

                    serialized_job = (
                        job_to_dict(
                            job
                        )
                    )

                    trace_entry[
                        "status"
                    ] = (
                        "handoff_requested"
                    )

                    trace_entry[
                        "job_id"
                    ] = (
                        job.job_id
                    )
"""


if marker not in source:
    raise RuntimeError(
        "No encontré el bloque esperado "
        "del Handoff."
    )


source = source.replace(
    marker,
    replacement,
    1,
)


# ============================================================
# AÑADIR JOB AL RETURN
# ============================================================


return_marker = """                        "handoff": (
                            serialized_handoff
                        ),
                        "capability_selection": {
"""


return_replacement = """                        "handoff": (
                            serialized_handoff
                        ),
                        "job_id": (
                            job.job_id
                        ),
                        "job": (
                            serialized_job
                        ),
                        "capability_selection": {
"""


if return_marker not in source:
    raise RuntimeError(
        "No encontré el return "
        "del Handoff."
    )


source = source.replace(
    return_marker,
    return_replacement,
    1,
)


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
    "HANDOFF → JOB CONECTADO"
)

print(
    "============================================"
)

print(
    "Compilación: OK"
)

print(
    "Backup:"
)

print(
    "src/unicore_agent_before_jobs.py"
)