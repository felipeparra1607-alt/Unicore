"""
Catálogo público MCP de UniCore.

Los módulos del backend pueden registrar muchas
capacidades para desarrollo y reutilización interna.

Este archivo decide qué Tools quedan realmente
expuestas al MCP Client o agente.

Ocultar una Tool aquí NO elimina su lógica Python.
Solo deja de publicarse como MCP Tool.
"""


TOOLS_HIDDEN_FROM_MCP = [
    # ========================================================
    # CHUNKS / RAG
    # ========================================================
    "list_document_chunks",
    "get_document_chunk",
    "semantic_search",
    "check_rag_readiness",
    "build_rag_context",

    # ========================================================
    # CONFIGURACIÓN DE IA
    # ========================================================
    "list_ai_providers",
    "check_ai_configuration",

    # ========================================================
    # CLASES
    # ========================================================
    "list_class_sessions",
    "get_class_session",
    "build_subject_class_timeline",

    # ========================================================
    # ESTUDIO
    # ========================================================
    "list_study_modes",
    "preview_study_context",
    "list_quiz_attempts",
    "get_subject_study_progress",

    # ========================================================
    # REPASO
    # ========================================================
    "list_review_items",

    # ========================================================
    # DASHBOARD / PLANIFICACIÓN
    # ========================================================
    "get_subject_dashboard",
    "get_daily_study_plan",

    # ========================================================
    # SESIONES DE ESTUDIO
    # ========================================================
    "list_study_sessions",
    "get_study_statistics",

    # ========================================================
    # TAREAS
    # ========================================================
    "list_academic_tasks",
    "get_academic_task",
    "get_task_priority_plan",
    "get_today_task_plan",

    # ========================================================
    # EVALUACIONES / NOTAS
    # ========================================================
    "list_assessments",
    "get_subject_grade_status",

    # ========================================================
    # PROFESOR / RÚBRICAS
    # ========================================================
    "list_professor_preferences",
    "list_rubric_criteria",

    # ========================================================
    # PREPARACIÓN DE TRABAJOS
    # ========================================================
    "build_assignment_preparation_context",
    "build_assignment_outline",

    # ========================================================
    # GAMIFICACIÓN
    # ========================================================
    "get_gamification_profile",
    "get_daily_missions",
    "list_boss_battles",

    # ========================================================
    # DASHBOARD / ANALYTICS / RIESGO
    # ========================================================
    "get_unicore_dashboard",
    "get_learning_analytics",
    "get_subject_academic_risk",
    "get_academic_risk_overview",

    # ========================================================
    # ASIGNATURAS
    # ========================================================
    "list_subjects",
    "get_subject",

    # ========================================================
    # PROFESORES
    # ========================================================
    "list_professors",
    "get_professor",

    # ========================================================
    # DOCUMENTOS
    # ========================================================
    "list_documents",
    "get_document",
    "get_document_text",
    "search_document_text",
]


def apply_public_tool_catalog(
    mcp,
) -> None:
    """
    Retira de la interfaz MCP las Tools que no forman
    parte del catálogo público de UniCore.

    Debe ejecutarse DESPUÉS de registrar todas las Tools.
    """

    for tool_name in TOOLS_HIDDEN_FROM_MCP:
        mcp.remove_tool(
            tool_name
        )