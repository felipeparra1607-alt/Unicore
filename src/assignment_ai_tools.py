import json
import re
import time
from typing import Any

from src.ai_config import get_ai_settings
from src.assignment_preparation_tools import (
    build_assignment_context_data,
)
from src.model_answer_tools import (
    build_sources_summary,
)
from src.providers import create_provider
from src.providers.base import GenerationRequest
from src.rag_tools import (
    build_context_text,
    calculate_evidence_status,
    retrieve_ranked_chunks,
    select_context_chunks,
)


def extract_json_object(
    text: str,
) -> dict[str, Any] | None:
    """Extrae JSON aunque venga dentro de Markdown."""

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

    try:
        result = json.loads(cleaned)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")

    if (
        first_brace == -1
        or last_brace == -1
        or last_brace <= first_brace
    ):
        return None

    try:
        result = json.loads(
            cleaned[
                first_brace:
                last_brace + 1
            ]
        )

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    return None


def build_assignment_rules_text(
    assignment_context: dict,
) -> str:
    """
    Convierte rúbrica, preferencias y feedback
    en texto para el modelo.
    """

    sections = []

    assessment = assignment_context[
        "assessment"
    ]

    sections.append(
        "EVALUACIÓN\n"
        f"Título: {assessment['title']}\n"
        f"Tipo: {assessment['assessment_type']}\n"
        f"Peso: {assessment['weight_percentage']} %\n"
        f"Descripción: "
        f"{assessment.get('description') or 'No registrada'}\n"
        f"Notas: "
        f"{assessment.get('notes') or 'No registradas'}"
    )

    rubric = assignment_context.get(
        "rubric",
        [],
    )

    if rubric:
        rubric_lines = []

        for criterion in rubric:
            rubric_lines.append(
                "- "
                f"{criterion['title']} "
                f"({criterion.get('weight_percentage')} %): "
                f"{criterion.get('description') or 'Sin descripción'}"
            )

        sections.append(
            "RÚBRICA OFICIAL\n"
            + "\n".join(rubric_lines)
        )

    preferences = assignment_context.get(
        "professor_preferences",
        [],
    )

    if preferences:
        preference_lines = []

        for preference in preferences:
            preference_lines.append(
                "- "
                f"{preference['category']}: "
                f"{preference['preference']} "
                f"[importancia={preference['importance']}, "
                f"confianza={preference['confidence']}, "
                f"origen={preference['source_type']}]"
            )

        sections.append(
            "PREFERENCIAS DEL PROFESOR\n"
            + "\n".join(preference_lines)
        )

    feedback = assignment_context.get(
        "previous_feedback",
        [],
    )

    if feedback:
        feedback_lines = []

        for item in feedback:
            feedback_lines.append(
                "- "
                f"{item['assessment_title']}: "
                f"{item['feedback']}"
            )

        sections.append(
            "FEEDBACK DE ENTREGAS ANTERIORES\n"
            + "\n".join(feedback_lines)
        )

    return "\n\n".join(sections)


def retrieve_assignment_rag(
    topic: str,
    subject_id: int,
    maximum_sources: int,
    maximum_context_characters: int,
    minimum_score: float,
    semantic_weight: float,
    redundancy_threshold: float,
) -> dict:
    """Recupera evidencia académica para el trabajo."""

    ranked_chunks = retrieve_ranked_chunks(
        query=topic,
        subject_id=subject_id,
        semantic_weight=semantic_weight,
    )

    selected_chunks = select_context_chunks(
        ranked_chunks=ranked_chunks,
        minimum_score=minimum_score,
        maximum_sources=maximum_sources,
        maximum_context_characters=(
            maximum_context_characters
        ),
        redundancy_threshold=(
            redundancy_threshold
        ),
    )

    return {
        "chunks": selected_chunks,
        "context": build_context_text(
            selected_chunks
        ),
        "evidence": calculate_evidence_status(
            selected_chunks
        ),
        "sources": build_sources_summary(
            selected_chunks
        ),
    }


def generation_metadata(
    generation_result,
    elapsed_ms: float,
) -> dict:
    """Normaliza metadatos comunes de generación."""

    return {
        "provider": generation_result.provider,
        "model": generation_result.model,
        "provider_called": (
            generation_result.metadata.get(
                "api_called",
                False,
            )
        ),
        "response_id": (
            generation_result.response_id
        ),
        "usage": {
            "input_tokens": (
                generation_result.input_tokens
            ),
            "output_tokens": (
                generation_result.output_tokens
            ),
            "total_tokens": (
                generation_result.total_tokens
            ),
        },
        "generation_status": {
            "response_status": (
                generation_result.response_status
            ),
            "incomplete_reason": (
                generation_result.incomplete_reason
            ),
            "truncated": (
                generation_result.truncated
            ),
        },
        "estimated_cost_usd": {
            "input": (
                generation_result
                .estimated_input_cost_usd
            ),
            "output": (
                generation_result
                .estimated_output_cost_usd
            ),
            "total": (
                generation_result
                .estimated_total_cost_usd
            ),
        },
        "duration_ms": elapsed_ms,
    }


def register_assignment_ai_tools(mcp) -> None:
    """Registra revisión y planificación inteligente."""

    @mcp.tool()
    def review_assignment_draft(
        subject_id: int,
        assessment_id: int,
        topic: str,
        draft_text: str,
        professor_id: int | None = None,
        provider: str | None = None,
        maximum_sources: int = 5,
        maximum_context_characters: int = 6000,
        maximum_output_tokens: int = 1200,
        minimum_score: float = 0.20,
        semantic_weight: float = 0.75,
        redundancy_threshold: float = 0.80,
    ) -> dict:
        """
        Revisa un borrador contra la rúbrica,
        preferencias y fuentes académicas.

        No reescribe automáticamente todo el trabajo.
        """

        started_at = time.perf_counter()

        clean_topic = topic.strip()
        clean_draft = draft_text.strip()

        if not clean_topic:
            return {
                "ok": False,
                "error": (
                    "El tema no puede estar vacío"
                ),
            }

        if len(clean_draft) < 50:
            return {
                "ok": False,
                "error": (
                    "El borrador es demasiado corto. "
                    "Introduce al menos 50 caracteres."
                ),
            }

        if len(clean_draft) > 50000:
            return {
                "ok": False,
                "error": (
                    "El borrador supera los "
                    "50000 caracteres."
                ),
            }

        assignment_context = (
            build_assignment_context_data(
                subject_id=subject_id,
                assessment_id=assessment_id,
                professor_id=professor_id,
            )
        )

        if not assignment_context.get("ok"):
            return assignment_context

        try:
            rag_result = retrieve_assignment_rag(
                topic=clean_topic,
                subject_id=subject_id,
                maximum_sources=maximum_sources,
                maximum_context_characters=(
                    maximum_context_characters
                ),
                minimum_score=minimum_score,
                semantic_weight=semantic_weight,
                redundancy_threshold=(
                    redundancy_threshold
                ),
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo recuperar "
                    "el contexto académico RAG"
                ),
                "technical_detail": str(error),
            }

        if not rag_result["evidence"]["sufficient"]:
            return {
                "ok": True,
                "reviewed": False,
                "reason": (
                    "No existe suficiente evidencia "
                    "académica para revisar el trabajo "
                    "con fuentes fiables."
                ),
                "evidence": rag_result["evidence"],
                "sources": rag_result["sources"],
                "provider_called": False,
            }

        rules_text = build_assignment_rules_text(
            assignment_context
        )

        system_message = (
            "Eres el revisor académico de UniCore. "
            "Tu tarea NO es escribir el trabajo completo. "
            "Debes analizar el borrador contra la rúbrica, "
            "las preferencias registradas del profesor y "
            "las fuentes académicas proporcionadas. "
            "Distingue siempre entre una regla oficial de "
            "rúbrica y una preferencia observada. "
            "No inventes requisitos. "
            "Para afirmaciones académicas sustentadas en "
            "los documentos utiliza [FUENTE 1], "
            "[FUENTE 2], etc. "
            "Devuelve exclusivamente JSON válido."
        )

        user_message = (
            f"TEMA DEL TRABAJO\n{clean_topic}\n\n"
            f"REQUISITOS Y CONTEXTO DEL PROFESOR\n"
            f"{rules_text}\n\n"
            f"FUENTES ACADÉMICAS\n"
            f"{rag_result['context']}\n\n"
            f"BORRADOR DEL ESTUDIANTE\n"
            f"{clean_draft}\n\n"
            "Devuelve exactamente una estructura JSON "
            "con este formato:\n"
            "{"
            '"overall_assessment":"",'
            '"strong_points":[""],'
            '"rubric_review":['
            "{"
            '"criterion":"",'
            '"status":"meets|partial|missing",'
            '"evidence_from_draft":"",'
            '"recommended_change":""'
            "}"
            "],"
            '"professor_alignment":['
            "{"
            '"preference":"",'
            '"status":"aligned|partial|not_aligned",'
            '"comment":""'
            "}"
            "],"
            '"academic_accuracy_issues":['
            "{"
            '"issue":"",'
            '"recommendation":"",'
            '"sources":["FUENTE 1"]'
            "}"
            "],"
            '"priority_changes":['
            "{"
            '"priority":1,'
            '"change":"",'
            '"reason":""'
            "}"
            "],"
            '"submission_readiness":"low|medium|high"'
            "}"
        )

        settings = get_ai_settings()

        try:
            selected_provider = create_provider(
                settings=settings,
                requested_provider=provider,
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo inicializar "
                    "el proveedor de IA"
                ),
                "technical_detail": str(error),
            }

        generation_result = (
            selected_provider.generate(
                GenerationRequest(
                    system_message=system_message,
                    user_message=user_message,
                    maximum_output_tokens=(
                        maximum_output_tokens
                    ),
                )
            )
        )

        elapsed_ms = round(
            (
                time.perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        if not generation_result.ok:
            return {
                "ok": False,
                "reviewed": False,
                "error": generation_result.error,
                "technical_detail": (
                    generation_result.technical_detail
                ),
                **generation_metadata(
                    generation_result,
                    elapsed_ms,
                ),
            }

        raw_text = generation_result.text or ""

        parsed = extract_json_object(
            raw_text
        )

        return {
            "ok": True,
            "reviewed": True,
            "topic": clean_topic,
            "subject_id": subject_id,
            "assessment_id": assessment_id,
            "review": (
                parsed
                if parsed is not None
                else raw_text
            ),
            "structured_output_valid": (
                parsed is not None
            ),
            "evidence": rag_result["evidence"],
            "source_count": len(
                rag_result["sources"]
            ),
            "sources": rag_result["sources"],
            "assignment_context_summary": {
                "rubric_criterion_count": len(
                    assignment_context["rubric"]
                ),
                "professor_preference_count": len(
                    assignment_context[
                        "professor_preferences"
                    ]
                ),
                "previous_feedback_count": len(
                    assignment_context[
                        "previous_feedback"
                    ]
                ),
            },
            **generation_metadata(
                generation_result,
                elapsed_ms,
            ),
        }

    @mcp.tool()
    def build_assignment_outline(
        subject_id: int,
        assessment_id: int,
        topic: str,
        professor_id: int | None = None,
        provider: str | None = None,
        maximum_sources: int = 5,
        maximum_context_characters: int = 6000,
        maximum_output_tokens: int = 1000,
        minimum_score: float = 0.20,
        semantic_weight: float = 0.75,
        redundancy_threshold: float = 0.80,
    ) -> dict:
        """
        Construye un esquema académico antes de escribir.

        No genera automáticamente el trabajo completo.
        """

        started_at = time.perf_counter()

        clean_topic = topic.strip()

        if not clean_topic:
            return {
                "ok": False,
                "error": (
                    "El tema no puede estar vacío"
                ),
            }

        assignment_context = (
            build_assignment_context_data(
                subject_id=subject_id,
                assessment_id=assessment_id,
                professor_id=professor_id,
            )
        )

        if not assignment_context.get("ok"):
            return assignment_context

        try:
            rag_result = retrieve_assignment_rag(
                topic=clean_topic,
                subject_id=subject_id,
                maximum_sources=maximum_sources,
                maximum_context_characters=(
                    maximum_context_characters
                ),
                minimum_score=minimum_score,
                semantic_weight=semantic_weight,
                redundancy_threshold=(
                    redundancy_threshold
                ),
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo recuperar "
                    "el contexto académico RAG"
                ),
                "technical_detail": str(error),
            }

        if not rag_result["evidence"]["sufficient"]:
            return {
                "ok": True,
                "generated": False,
                "reason": (
                    "No existe suficiente evidencia "
                    "académica para preparar un esquema "
                    "fundamentado."
                ),
                "evidence": rag_result["evidence"],
                "sources": rag_result["sources"],
                "provider_called": False,
            }

        rules_text = build_assignment_rules_text(
            assignment_context
        )

        system_message = (
            "Eres el planificador académico de UniCore. "
            "Debes diseñar la estructura de un trabajo, "
            "pero no escribir el trabajo completo. "
            "Usa la rúbrica como requisito oficial. "
            "Las preferencias del profesor son orientación "
            "adicional y deben respetar su nivel de confianza. "
            "Usa exclusivamente las fuentes académicas "
            "proporcionadas para proponer contenido factual. "
            "Incluye citas [FUENTE N] cuando relaciones "
            "una sección con contenido académico. "
            "Devuelve exclusivamente JSON válido."
        )

        user_message = (
            f"TEMA DEL TRABAJO\n{clean_topic}\n\n"
            f"REQUISITOS Y CONTEXTO DEL PROFESOR\n"
            f"{rules_text}\n\n"
            f"FUENTES ACADÉMICAS\n"
            f"{rag_result['context']}\n\n"
            "Crea un esquema y devuelve exactamente:\n"
            "{"
            '"recommended_focus":"",'
            '"working_thesis":"",'
            '"sections":['
            "{"
            '"order":1,'
            '"title":"",'
            '"purpose":"",'
            '"key_points":[""],'
            '"rubric_criteria":[""],'
            '"professor_preferences":[""],'
            '"sources":["FUENTE 1"]'
            "}"
            "],"
            '"things_to_avoid":[""],'
            '"final_checklist":[""]'
            "}"
        )

        settings = get_ai_settings()

        try:
            selected_provider = create_provider(
                settings=settings,
                requested_provider=provider,
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo inicializar "
                    "el proveedor de IA"
                ),
                "technical_detail": str(error),
            }

        generation_result = (
            selected_provider.generate(
                GenerationRequest(
                    system_message=system_message,
                    user_message=user_message,
                    maximum_output_tokens=(
                        maximum_output_tokens
                    ),
                )
            )
        )

        elapsed_ms = round(
            (
                time.perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        if not generation_result.ok:
            return {
                "ok": False,
                "generated": False,
                "error": generation_result.error,
                "technical_detail": (
                    generation_result.technical_detail
                ),
                **generation_metadata(
                    generation_result,
                    elapsed_ms,
                ),
            }

        raw_text = generation_result.text or ""

        parsed = extract_json_object(
            raw_text
        )

        return {
            "ok": True,
            "generated": True,
            "topic": clean_topic,
            "subject_id": subject_id,
            "assessment_id": assessment_id,
            "outline": (
                parsed
                if parsed is not None
                else raw_text
            ),
            "structured_output_valid": (
                parsed is not None
            ),
            "evidence": rag_result["evidence"],
            "source_count": len(
                rag_result["sources"]
            ),
            "sources": rag_result["sources"],
            "assignment_context_summary": {
                "rubric_criterion_count": len(
                    assignment_context["rubric"]
                ),
                "professor_preference_count": len(
                    assignment_context[
                        "professor_preferences"
                    ]
                ),
                "previous_feedback_count": len(
                    assignment_context[
                        "previous_feedback"
                    ]
                ),
            },
            **generation_metadata(
                generation_result,
                elapsed_ms,
            ),
        }