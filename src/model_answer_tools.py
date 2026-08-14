import re
import time

from src.ai_config import get_ai_settings
from src.providers import (
    available_providers,
    create_provider,
)
from src.providers.base import GenerationRequest
from src.rag_answer_tools import (
    build_extractive_answer,
    build_model_messages,
)
from src.rag_tools import (
    build_context_text,
    calculate_evidence_status,
    retrieve_ranked_chunks,
    select_context_chunks,
)


def contains_source_citation(text: str) -> bool:
    """Comprueba si la respuesta contiene al menos una cita."""

    return bool(
        re.search(
            r"\[FUENTE\s+\d+\]",
            text,
            flags=re.IGNORECASE,
        )
    )


def build_sources_summary(
    selected_chunks,
) -> list[dict]:
    """Convierte los chunks recuperados en fuentes trazables."""

    return [
        {
            "source_number": source_number,
            "document_id": result.document.id,
            "document_title": result.document.title,
            "file_type": result.document.file_type,
            "chunk_id": result.chunk.id,
            "chunk_index": result.chunk.chunk_index,
            "source_label": result.chunk.source_label,
            "score": round(
                result.combined_score,
                6,
            ),
            "semantic_score": round(
                result.semantic_score,
                6,
            ),
            "lexical_score": round(
                result.lexical_score,
                6,
            ),
        }
        for source_number, result in enumerate(
            selected_chunks,
            start=1,
        )
    ]


def register_model_answer_tools(mcp) -> None:
    """Registra las tools de proveedores y respuestas generativas."""

    @mcp.tool()
    def list_ai_providers() -> dict:
        """Lista los proveedores implementados actualmente."""

        settings = get_ai_settings()

        return {
            "ok": True,
            "configured_provider": settings.provider,
            "configured_model": settings.openai_model,
            "providers": available_providers(),
        }

    @mcp.tool()
    def check_ai_configuration() -> dict:
        """
        Comprueba la configuración sin mostrar claves privadas.
        """

        settings = get_ai_settings()

        ready = True
        reason = "Configuración preparada"

        if (
            settings.provider == "openai"
            and not settings.openai_api_key
        ):
            ready = False
            reason = "Falta configurar OPENAI_API_KEY"

        if settings.provider not in {
            "mock",
            "openai",
        }:
            ready = False
            reason = (
                "El proveedor configurado no está implementado"
            )

        configured_model = (
            settings.openai_model
            if settings.provider == "openai"
            else "mock-local-v1"
        )

        return {
            "ok": True,
            "ready": ready,
            "provider": settings.provider,
            "model": configured_model,
            "has_openai_api_key": bool(
                settings.openai_api_key
            ),
            "maximum_output_tokens": (
                settings.maximum_output_tokens
            ),
            "fallback_to_extractive": (
                settings.fallback_to_extractive
            ),
            "reason": reason,
        }

    @mcp.tool()
    def answer_with_model(
        query: str,
        subject_id: int | None = None,
        document_id: int | None = None,
        provider: str | None = None,
        maximum_sources: int = 5,
        maximum_context_characters: int = 6000,
        maximum_output_tokens: int | None = None,
        minimum_score: float = 0.20,
        semantic_weight: float = 0.75,
        redundancy_threshold: float = 0.80,
        fallback_to_extractive: bool | None = None,
    ) -> dict:
        """
        Responde usando RAG y un proveedor intercambiable.

        Proveedores actuales:
        - mock: prueba local gratuita.
        - openai: generación real mediante API.
        """

        started_at = time.perf_counter()
        settings = get_ai_settings()
        clean_query = query.strip()

        if not clean_query:
            return {
                "ok": False,
                "error": "La pregunta no puede estar vacía",
            }

        if maximum_sources < 1 or maximum_sources > 20:
            return {
                "ok": False,
                "error": (
                    "maximum_sources debe estar entre 1 y 20"
                ),
            }

        if (
            maximum_context_characters < 500
            or maximum_context_characters > 50000
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_context_characters debe estar "
                    "entre 500 y 50000"
                ),
            }

        effective_maximum_output_tokens = (
            maximum_output_tokens
            if maximum_output_tokens is not None
            else settings.maximum_output_tokens
        )

        if (
            effective_maximum_output_tokens < 100
            or effective_maximum_output_tokens > 10000
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_output_tokens debe estar "
                    "entre 100 y 10000"
                ),
            }

        effective_fallback = (
            fallback_to_extractive
            if fallback_to_extractive is not None
            else settings.fallback_to_extractive
        )

        try:
            ranked_chunks = retrieve_ranked_chunks(
                query=clean_query,
                subject_id=subject_id,
                semantic_weight=semantic_weight,
                document_id=document_id,
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

        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo recuperar el contexto RAG"
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
            elapsed_ms = round(
                (
                    time.perf_counter()
                    - started_at
                )
                * 1000,
                2,
            )

            return {
                "ok": True,
                "answered": False,
                "query": clean_query,
                "answer": (
                    "No hay evidencia suficientemente relevante "
                    "en los documentos para responder con "
                    "seguridad."
                ),
                "evidence": evidence,
                "source_count": len(sources),
                "sources": sources,
                "provider_called": False,
                "duration_ms": elapsed_ms,
            }

        context = build_context_text(
            selected_chunks
        )

        instructions = (
            "Responde exclusivamente con la información del "
            "contexto recuperado. Cita cada afirmación importante "
            "mediante [FUENTE 1], [FUENTE 2], etc. No inventes "
            "hechos, ejemplos ni referencias. Cuando las fuentes "
            "no permitan responder una parte, indícalo claramente. "
            "Redacta una respuesta clara, natural y útil para un "
            "estudiante universitario."
        )

        messages = build_model_messages(
            query=clean_query,
            context=context,
            instructions=instructions,
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
                "configured_provider": settings.provider,
            }

        generation_request = GenerationRequest(
            system_message=messages["system"],
            user_message=messages["user"],
            maximum_output_tokens=(
                effective_maximum_output_tokens
            ),
        )

        generation_result = selected_provider.generate(
            generation_request
        )

        fallback_used = False
        final_answer = generation_result.text

        if (
            not generation_result.ok
            and effective_fallback
        ):
            extractive_result = build_extractive_answer(
                query=clean_query,
                selected_chunks=selected_chunks,
                maximum_sentences=5,
            )

            final_answer = extractive_result["answer"]
            fallback_used = True

        elapsed_ms = round(
            (
                time.perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        if (
            not generation_result.ok
            and not fallback_used
        ):
            return {
                "ok": False,
                "answered": False,
                "query": clean_query,
                "error": generation_result.error,
                "technical_detail": (
                    generation_result.technical_detail
                ),
                "provider": generation_result.provider,
                "model": generation_result.model,
                "evidence": evidence,
                "source_count": len(sources),
                "sources": sources,
                "duration_ms": elapsed_ms,
                "fallback_used": False,
            }

        final_answer = final_answer or ""

        return {
            "ok": True,
            "answered": True,
            "query": clean_query,
            "answer": final_answer,
            "answer_has_citations": (
                contains_source_citation(final_answer)
            ),
            "evidence": evidence,
            "source_count": len(sources),
            "context_characters": len(context),
            "input_characters": (
                len(messages["system"])
                + len(messages["user"])
            ),
            "output_characters": len(final_answer),
            "sources": sources,
            "provider": generation_result.provider,
            "model": generation_result.model,
            "provider_called": (
                generation_result.metadata.get(
                    "api_called",
                    False,
                )
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
        generation_result.estimated_input_cost_usd
    ),
    "output": (
        generation_result.estimated_output_cost_usd
    ),
    "total": (
        generation_result.estimated_total_cost_usd
    ),
},
"duration_ms": elapsed_ms,
            "fallback_used": fallback_used,
            "provider_error": (
                generation_result.error
                if fallback_used
                else None
            ),
            "settings": {
                "maximum_sources": maximum_sources,
                "maximum_context_characters": (
                    maximum_context_characters
                ),
                "maximum_output_tokens": (
                    effective_maximum_output_tokens
                ),
                "minimum_score": minimum_score,
                "semantic_weight": semantic_weight,
                "redundancy_threshold": (
                    redundancy_threshold
                ),
            },
        }
