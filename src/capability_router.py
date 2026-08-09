from __future__ import annotations

import unicodedata

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySelection:
    profile: str

    tool_names: frozenset[str]

    direct_resource_uris: frozenset[str]

    template_fragments: frozenset[str]


def normalize_text(
    value: str,
) -> str:
    text = value.strip().casefold()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    return "".join(
        character
        for character in text
        if not unicodedata.combining(
            character
        )
    )


# ============================================================
# CAPACIDADES BASE
# ============================================================
#
# Se incluyen siempre.
#
# "subjects" es barato y permite resolver subject_id.
# health_check queda disponible para diagnóstico.
# ============================================================


BASE_TOOLS = frozenset({
    "health_check",
})


BASE_RESOURCES = frozenset({
    "unicore://subjects",
})


# ============================================================
# PERFILES
# ============================================================
#
# IMPORTANTE:
#
# Un perfil NO decide qué Tool ejecutar.
#
# Solo reduce el espacio de capacidades que el agente
# necesita considerar.
# ============================================================


PROFILES = {
    "planning": CapabilitySelection(
        profile="planning",
        tool_names=frozenset({
            "recommend_next_actions",
            "get_review_plan",
        }),
        direct_resource_uris=frozenset({
            "unicore://today",
            "unicore://tasks",
        }),
        template_fragments=frozenset({
            "/tasks",
            "/reviews",
            "/assessments",
            "/knowledge",
        }),
    ),

    "knowledge": CapabilitySelection(
        profile="knowledge",
        tool_names=frozenset({
            "get_quiz_attempt",
            "get_review_plan",
        }),
        direct_resource_uris=frozenset(),
        template_fragments=frozenset({
            "/knowledge",
            "/study",
            "/reviews",
            "/analytics",
            "/risk",
            "/dashboard",
        }),
    ),

    "documents": CapabilitySelection(
        profile="documents",
        tool_names=frozenset({
            "answer_with_rag",
            "hybrid_search",
            "get_rag_source",
        }),
        direct_resource_uris=frozenset({
            "unicore://documents",
        }),
        template_fragments=frozenset({
            "/documents",
        }),
    ),

    "grades": CapabilitySelection(
        profile="grades",
        tool_names=frozenset({
            "simulate_assessment_grade",
        }),
        direct_resource_uris=frozenset(),
        template_fragments=frozenset({
            "/grade",
            "/assessments",
        }),
    ),

    "reviews": CapabilitySelection(
        profile="reviews",
        tool_names=frozenset({
            "get_review_plan",
            "get_quiz_attempt",
        }),
        direct_resource_uris=frozenset(),
        template_fragments=frozenset({
            "/reviews",
            "/knowledge",
            "/study",
        }),
    ),

    "professor": CapabilitySelection(
        profile="professor",
        tool_names=frozenset(),
        direct_resource_uris=frozenset(),
        template_fragments=frozenset({
            "/professor",
        }),
    ),

    "study": CapabilitySelection(
        profile="study",
        tool_names=frozenset({
            "get_quiz_attempt",
            "get_review_plan",
        }),
        direct_resource_uris=frozenset(),
        template_fragments=frozenset({
            "/study",
            "/reviews",
            "/knowledge",
        }),
    ),

    "tasks": CapabilitySelection(
        profile="tasks",
        tool_names=frozenset({
            "recommend_next_actions",
        }),
        direct_resource_uris=frozenset({
            "unicore://tasks",
        }),
        template_fragments=frozenset({
            "/tasks",
        }),
    ),
}


# ============================================================
# ESCRITURAS
# ============================================================


WRITE_TASK_TOOLS = frozenset({
    "create_academic_task",
    "update_academic_task",
    "complete_academic_task",
})


WRITE_STUDY_TOOLS = frozenset({
    "create_study_session",
})


WRITE_QUIZ_TOOLS = frozenset({
    "create_quiz_attempt",
    "submit_quiz_attempt",
})


WRITE_REVIEW_TOOLS = frozenset({
    "submit_review_result",
    "sync_knowledge_map_tool",
})


# ============================================================
# DETECCIÓN GRUESA DEL DOMINIO
# ============================================================


def contains_any(
    text: str,
    expressions: tuple[str, ...],
) -> bool:
    return any(
        expression in text
        for expression in expressions
    )


def detect_profiles(
    user_request: str,
) -> set[str]:
    """
    Clasificación local y barata.

    NO selecciona Tools concretas.

    Puede devolver varios perfiles si la petición
    mezcla objetivos.
    """

    text = normalize_text(
        user_request
    )

    profiles: set[str] = set()

    if contains_any(
        text,
        (
            "que hago",
            "que deberia hacer",
            "que estudiar",
            "que deberia estudiar",
            "tengo 30 minutos",
            "tengo 45 minutos",
            "tengo 60 minutos",
            "tengo una hora",
            "tengo dos horas",
            "prioridad",
            "prioridades",
            "plan de hoy",
            "planificar",
        ),
    ):
        profiles.add(
            "planning"
        )

    if contains_any(
        text,
        (
            "concepto",
            "conceptos",
            "dominio",
            "domino",
            "flojo",
            "flojos",
            "debil",
            "debiles",
            "fortaleza",
            "fortalezas",
            "knowledge",
            "como voy",
            "progreso de aprendizaje",
        ),
    ):
        profiles.add(
            "knowledge"
        )

    if contains_any(
        text,
        (
            "documento",
            "documentos",
            "apuntes",
            "archivo",
            "archivos",
            "segun mis documentos",
            "segun mis apuntes",
            "busca",
            "buscar",
            "rag",
        ),
    ):
        profiles.add(
            "documents"
        )

    if contains_any(
        text,
        (
            "nota",
            "notas",
            "calificacion",
            "calificaciones",
            "evaluacion",
            "evaluaciones",
            "examen",
            "examenes",
            "saco un",
            "sacara un",
            "simular",
            "simulacion",
            "media",
        ),
    ):
        profiles.add(
            "grades"
        )

    if contains_any(
        text,
        (
            "repasar",
            "repaso",
            "reviews",
            "review",
            "revision",
        ),
    ):
        profiles.add(
            "reviews"
        )

    if contains_any(
        text,
        (
            "profesor",
            "profesora",
            "docente",
            "rubrica",
            "rubricas",
        ),
    ):
        profiles.add(
            "professor"
        )

    if contains_any(
        text,
        (
            "estudiar",
            "estudio",
            "sesion de estudio",
            "quiz",
            "test",
            "preguntas",
        ),
    ):
        profiles.add(
            "study"
        )

    if contains_any(
        text,
        (
            "tarea",
            "tareas",
            "pendiente",
            "pendientes",
            "assignment",
            "trabajo",
            "entrega",
        ),
    ):
        profiles.add(
            "tasks"
        )

    return profiles


def build_capability_selection(
    user_request: str,
    allow_writes: bool,
) -> dict:
    """
    Construye el subconjunto inicial de capacidades.

    Si no reconoce con suficiente claridad el dominio,
    usa fallback amplio para no reducir recall.
    """

    profiles = detect_profiles(
        user_request
    )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------
    #
    # Si no reconocemos ninguna familia, no queremos
    # bloquear al agente.
    #
    # En ese caso indicamos broad_fallback=True y
    # unicore_agent conservará su catálogo anterior.
    # --------------------------------------------------------

    if not profiles:
        return {
            "profiles": [
                "broad_fallback"
            ],
            "broad_fallback": True,
            "tool_names": set(),
            "direct_resource_uris": set(),
            "template_fragments": set(),
        }

    tools = set(
        BASE_TOOLS
    )

    resources = set(
        BASE_RESOURCES
    )

    template_fragments: set[str] = set()

    for profile_name in profiles:
        selection = PROFILES[
            profile_name
        ]

        tools.update(
            selection.tool_names
        )

        resources.update(
            selection.direct_resource_uris
        )

        template_fragments.update(
            selection.template_fragments
        )

    # --------------------------------------------------------
    # ESCRITURAS
    # --------------------------------------------------------

    if allow_writes:
        text = normalize_text(
            user_request
        )

        if "tarea" in text:
            tools.update(
                WRITE_TASK_TOOLS
            )

        if (
            "sesion" in text
            and "estudio" in text
        ):
            tools.update(
                WRITE_STUDY_TOOLS
            )

        if contains_any(
            text,
            (
                "quiz",
                "test",
            ),
        ):
            tools.update(
                WRITE_QUIZ_TOOLS
            )

        if contains_any(
            text,
            (
                "repaso",
                "review",
            ),
        ):
            tools.update(
                WRITE_REVIEW_TOOLS
            )

    return {
        "profiles": sorted(
            profiles
        ),
        "broad_fallback": False,
        "tool_names": tools,
        "direct_resource_uris": (
            resources
        ),
        "template_fragments": (
            template_fragments
        ),
    }


def filter_tools(
    tools: list[dict],
    selection: dict,
) -> list[dict]:
    if selection[
        "broad_fallback"
    ]:
        return tools

    allowed = selection[
        "tool_names"
    ]

    return [
        tool
        for tool in tools
        if tool.get(
            "name"
        ) in allowed
    ]


def filter_resources(
    resources: list[dict],
    selection: dict,
) -> list[dict]:
    if selection[
        "broad_fallback"
    ]:
        return resources

    allowed = selection[
        "direct_resource_uris"
    ]

    return [
        resource
        for resource in resources
        if resource.get(
            "uri"
        ) in allowed
    ]


def filter_templates(
    templates: list[dict],
    selection: dict,
) -> list[dict]:
    if selection[
        "broad_fallback"
    ]:
        return templates

    fragments = selection[
        "template_fragments"
    ]

    result = []

    for template in templates:
        uri_template = str(
            template.get(
                "uri_template",
                "",
            )
        )

        if any(
            fragment
            in uri_template
            for fragment in fragments
        ):
            result.append(
                template
            )

    return result