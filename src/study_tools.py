import json
import re
import time
from typing import Any

from src.ai_config import get_ai_settings
from src.model_answer_tools import build_sources_summary
from src.providers import create_provider
from src.providers.base import GenerationRequest
from src.rag_tools import (
    build_context_text,
    calculate_evidence_status,
    retrieve_ranked_chunks,
    select_context_chunks,
)


SUPPORTED_STUDY_MODES = {
    "explanation",
    "summary",
    "quiz",
    "flashcards",
    "quick_review",
}


def study_mode_instructions(
    mode: str,
    item_count: int,
    difficulty: str,
) -> str:
    """Devuelve instrucciones específicas para cada modo."""

    common_rules = (
        "Utiliza únicamente el contexto recuperado. "
        "No inventes información. "
        "Conserva la terminología de las fuentes. "
        "Cita las afirmaciones mediante [FUENTE 1], "
        "[FUENTE 2], etc. "
    )

    if mode == "explanation":
        return (
            common_rules
            + "Explica el tema de forma clara y progresiva. "
            "Empieza por la idea principal, desarrolla los "
            "conceptos y termina con una conclusión breve. "
            f"Adapta la dificultad al nivel {difficulty}."
        )

    if mode == "summary":
        return (
            common_rules
            + "Crea un resumen académico organizado. "
            "Incluye conceptos principales, relaciones importantes "
            "y una conclusión. Evita repeticiones."
        )

    if mode == "quick_review":
        return (
            common_rules
            + "Crea un repaso rápido para estudiar antes de una "
            "clase o examen. Usa apartados breves: ideas esenciales, "
            "conceptos que no deben confundirse y preguntas de "
            "autocomprobación."
        )

    if mode == "quiz":
        return (
            common_rules
            + f"Crea exactamente {item_count} preguntas tipo test. "
            "Cada pregunta debe tener cuatro opciones, una sola "
            "respuesta correcta y una explicación breve. "
            "Devuelve únicamente JSON válido con esta estructura: "
            '{"items":[{"question":"",'
            '"options":["","","",""],'
            '"correct_index":0,'
            '"explanation":"",'
            '"sources":["FUENTE 1"]}]}. '
            "correct_index debe ser 0, 1, 2 o 3."
        )

    if mode == "flashcards":
        return (
            common_rules
            + f"Crea exactamente {item_count} flashcards. "
            "Devuelve únicamente JSON válido con esta estructura: "
            '{"items":[{"front":"","back":"",'
            '"sources":["FUENTE 1"]}]}. '
            "El frente debe plantear una pregunta o concepto y "
            "el reverso debe contener una respuesta breve y precisa."
        )

    raise ValueError(
        f"Modo de estudio no compatible: {mode}"
    )


def extract_json_object(text: str) -> dict[str, Any] | None:
    """
    Intenta extraer un objeto JSON aunque el modelo añada
    accidentalmente un bloque Markdown.
    """

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
        parsed = json.loads(cleaned)

        if isinstance(parsed, dict):
            return parsed

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
        parsed = json.loads(
            cleaned[first_brace:last_brace + 1]
        )

        return parsed if isinstance(parsed, dict) else None

    except json.JSONDecodeError:
        return None


def validate_quiz(
    data: dict[str, Any],
    expected_count: int,
) -> tuple[bool, str | None]:
    """Valida la estructura de un quiz generado."""

    items = data.get("items")

    if not isinstance(items, list):
        return False, "Falta la lista items"

    if len(items) != expected_count:
        return (
            False,
            "El número de preguntas no coincide con lo solicitado",
        )

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            return False, f"La pregunta {index} no es un objeto"

        if not isinstance(item.get("question"), str):
            return False, f"Falta question en la pregunta {index}"

        options = item.get("options")

        if (
            not isinstance(options, list)
            or len(options) != 4
            or not all(
                isinstance(option, str)
                for option in options
            )
        ):
            return (
                False,
                f"La pregunta {index} debe tener cuatro opciones",
            )

        if item.get("correct_index") not in {0, 1, 2, 3}:
            return (
                False,
                f"correct_index inválido en la pregunta {index}",
            )

        if not isinstance(item.get("explanation"), str):
            return (
                False,
                f"Falta explanation en la pregunta {index}",
            )

    return True, None


def validate_flashcards(
    data: dict[str, Any],
    expected_count: int,
) -> tuple[bool, str | None]:
    """Valida la estructura de flashcards."""

    items = data.get("items")

    if not isinstance(items, list):
        return False, "Falta la lista items"

    if len(items) != expected_count:
        return (
            False,
            "El número de flashcards no coincide con lo solicitado",
        )

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            return False, f"La flashcard {index} no es un objeto"

        if not isinstance(item.get("front"), str):
            return False, f"Falta front en la flashcard {index}"

        if not isinstance(item.get("back"), str):
            return False, f"Falta back en la flashcard {index}"

    return True, None


def register_study_tools(mcp) -> None:
    """Registra las tools del primer motor de estudio."""

    @mcp.tool()
    def list_study_modes() -> dict:
        """Lista los modos de estudio disponibles."""

        return {
            "ok": True,
            "modes": [
                {
                    "mode": "explanation",
                    "description": (
                        "Explicación progresiva de un tema"
                    ),
                    "structured_output": False,
                },
                {
                    "mode": "summary",
                    "description": (
                        "Resumen académico fundamentado"
                    ),
                    "structured_output": False,
                },
                {
                    "mode": "quick_review",
                    "description": (
                        "Repaso breve antes de clase o examen"
                    ),
                    "structured_output": False,
                },
                {
                    "mode": "quiz",
                    "description": (
                        "Preguntas tipo test con respuestas"
                    ),
                    "structured_output": True,
                },
                {
                    "mode": "flashcards",
                    "description": (
                        "Tarjetas de pregunta y respuesta"
                    ),
                    "structured_output": True,
                },
            ],
        }

    @mcp.tool()
    def preview_study_context(
        topic: str,
        subject_id: int,
        document_id: int | None = None,
        maximum_sources: int = 4,
        maximum_context_characters: int = 6000,
        minimum_score: float = 0.20,
        semantic_weight: float = 0.75,
        redundancy_threshold: float = 0.80,
    ) -> dict:
        """
        Recupera las fuentes que utilizaría el motor de estudio
        sin llamar a ningún modelo.
        """

        clean_topic = topic.strip()

        if not clean_topic:
            return {
                "ok": False,
                "error": "El tema no puede estar vacío",
            }

        if maximum_sources < 1 or maximum_sources > 4:
            return {
                "ok": False,
                "error": "maximum_sources debe estar entre 1 y 4",
            }

        try:
            ranked_chunks = retrieve_ranked_chunks(
                query=clean_topic,
                subject_id=subject_id,
                document_id=document_id,
                semantic_weight=semantic_weight,
            )

            selected_chunks = select_context_chunks(
                ranked_chunks=ranked_chunks,
                minimum_score=minimum_score,
                maximum_sources=maximum_sources,
                maximum_context_characters=(
                    maximum_context_characters
                ),
                redundancy_threshold=redundancy_threshold,
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo recuperar el contexto de estudio"
                ),
                "technical_detail": str(error),
            }

        context = build_context_text(selected_chunks)
        evidence = calculate_evidence_status(selected_chunks)

        return {
            "ok": True,
            "topic": clean_topic,
            "subject_id": subject_id,
            "document_id": document_id,
            "evidence": evidence,
            "source_count": len(selected_chunks),
            "context_characters": len(context),
            "sources": build_sources_summary(
                selected_chunks
            ),
            "context": context,
            "provider_called": False,
            "estimated_cost_usd": 0,
        }

    @mcp.tool()
    def generate_study_material(
        topic: str,
        subject_id: int,
        mode: str = "explanation",
        difficulty: str = "intermedio",
        item_count: int = 5,
        document_id: int | None = None,
        provider: str | None = None,
        maximum_sources: int = 4,
        maximum_context_characters: int = 6000,
        maximum_output_tokens: int | None = None,
        minimum_score: float = 0.20,
        semantic_weight: float = 0.75,
        redundancy_threshold: float = 0.80,
    ) -> dict:
        """
        Genera materiales de estudio fundamentados en documentos.

        Modos:
        explanation, summary, quick_review, quiz y flashcards.
        """

        started_at = time.perf_counter()

        clean_topic = topic.strip()
        clean_mode = mode.strip().casefold()
        clean_difficulty = difficulty.strip().casefold()

        if not clean_topic:
            return {
                "ok": False,
                "error": "El tema no puede estar vacío",
            }

        if clean_mode not in SUPPORTED_STUDY_MODES:
            return {
                "ok": False,
                "error": (
                    "Modo no compatible. Usa explanation, summary, "
                    "quick_review, quiz o flashcards"
                ),
            }

        if clean_difficulty not in {
            "básico",
            "basico",
            "intermedio",
            "avanzado",
        }:
            return {
                "ok": False,
                "error": (
                    "difficulty debe ser básico, intermedio "
                    "o avanzado"
                ),
            }

        if item_count < 1 or item_count > 30:
            return {
                "ok": False,
                "error": (
                    "item_count debe estar entre 1 y 30"
                ),
            }

        if maximum_sources < 1 or maximum_sources > 4:
            return {
                "ok": False,
                "error": (
                    "maximum_sources debe estar entre 1 y 4"
                ),
            }

        settings = get_ai_settings()

        effective_output_tokens = (
            maximum_output_tokens
            if maximum_output_tokens is not None
            else settings.maximum_output_tokens
        )

        if (
            effective_output_tokens < 100
            or effective_output_tokens > 10000
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_output_tokens debe estar "
                    "entre 100 y 10000"
                ),
            }

        try:
            ranked_chunks = retrieve_ranked_chunks(
                query=clean_topic,
                subject_id=subject_id,
                document_id=document_id,
                semantic_weight=semantic_weight,
            )

            selected_chunks = select_context_chunks(
                ranked_chunks=ranked_chunks,
                minimum_score=minimum_score,
                maximum_sources=maximum_sources,
                maximum_context_characters=(
                    maximum_context_characters
                ),
                redundancy_threshold=redundancy_threshold,
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo recuperar el contexto de estudio"
                ),
                "technical_detail": str(error),
            }

        evidence = calculate_evidence_status(
            selected_chunks
        )

        sources = build_sources_summary(
            selected_chunks
        )

        if not evidence["sufficient"]:
            return {
                "ok": True,
                "generated": False,
                "topic": clean_topic,
                "mode": clean_mode,
                "message": (
                    "No hay evidencia suficientemente relevante "
                    "en los documentos para generar este material."
                ),
                "evidence": evidence,
                "source_count": len(sources),
                "sources": sources,
                "provider_called": False,
            }

        context = build_context_text(
            selected_chunks
        )

        instructions = study_mode_instructions(
            mode=clean_mode,
            item_count=item_count,
            difficulty=clean_difficulty,
        )

        system_message = (
            "Eres el motor de estudio académico de UniCore. "
            "Tu función es ayudar al estudiante a aprender desde "
            "sus propios documentos. "
            f"{instructions}"
        )

        user_message = (
            f"Tema solicitado:\n{clean_topic}\n\n"
            f"Nivel:\n{clean_difficulty}\n\n"
            f"Contexto académico:\n{context}"
        )

        try:
            selected_provider = create_provider(
                settings=settings,
                requested_provider=provider,
            )

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo inicializar el proveedor"
                ),
                "technical_detail": str(error),
            }

        generation_result = selected_provider.generate(
            GenerationRequest(
                system_message=system_message,
                user_message=user_message,
                maximum_output_tokens=(
                    effective_output_tokens
                ),
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
                "topic": clean_topic,
                "mode": clean_mode,
                "error": generation_result.error,
                "technical_detail": (
                    generation_result.technical_detail
                ),
                "provider": generation_result.provider,
                "model": generation_result.model,
                "evidence": evidence,
                "sources": sources,
                "duration_ms": elapsed_ms,
            }

        raw_text = generation_result.text or ""
        structured_data = None
        validation = {
            "required": clean_mode in {
                "quiz",
                "flashcards",
            },
            "valid": True,
            "error": None,
        }

        if clean_mode in {"quiz", "flashcards"}:
            structured_data = extract_json_object(
                raw_text
            )

            if structured_data is None:
                validation = {
                    "required": True,
                    "valid": False,
                    "error": (
                        "El proveedor no devolvió JSON válido"
                    ),
                }

            elif clean_mode == "quiz":
                is_valid, validation_error = validate_quiz(
                    structured_data,
                    expected_count=item_count,
                )

                validation = {
                    "required": True,
                    "valid": is_valid,
                    "error": validation_error,
                }

            else:
                is_valid, validation_error = (
                    validate_flashcards(
                        structured_data,
                        expected_count=item_count,
                    )
                )

                validation = {
                    "required": True,
                    "valid": is_valid,
                    "error": validation_error,
                }

        return {
            "ok": True,
            "generated": True,
            "topic": clean_topic,
            "subject_id": subject_id,
            "document_id": document_id,
            "mode": clean_mode,
            "difficulty": clean_difficulty,
            "item_count": (
                item_count
                if clean_mode in {"quiz", "flashcards"}
                else None
            ),
            "content": (
                structured_data
                if structured_data is not None
                else raw_text
            ),
            "raw_text": (
                raw_text
                if structured_data is not None
                else None
            ),
            "structured_output_validation": validation,
            "evidence": evidence,
            "source_count": len(sources),
            "context_characters": len(context),
            "sources": sources,
            "provider": generation_result.provider,
            "model": generation_result.model,
            "provider_called": generation_result.metadata.get(
                "api_called",
                False,
            ),
            "response_id": generation_result.response_id,
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
                "truncated": generation_result.truncated,
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
            "task_metadata": {
                "task_family": "study",
                "task_type": clean_mode,
                "difficulty": clean_difficulty,
                "modality": "text",
            },
        }
