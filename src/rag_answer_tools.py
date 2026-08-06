import re
from dataclasses import dataclass

from src.rag_tools import (
    build_context_text,
    calculate_evidence_status,
    retrieve_ranked_chunks,
    select_context_chunks,
)


@dataclass
class ExtractiveSentence:
    """Representa una frase seleccionada desde una fuente."""

    text: str
    source_number: int
    score: float


def split_into_sentences(text: str) -> list[str]:
    """Divide un texto en frases legibles."""

    cleaned_text = re.sub(
        r"\n{2,}",
        "\n",
        text.strip(),
    )

    raw_sentences = re.split(
        r"(?<=[.!?])\s+|\n+",
        cleaned_text,
    )

    return [
        sentence.strip()
        for sentence in raw_sentences
        if len(sentence.strip()) >= 25
    ]


def normalize_sentence(text: str) -> str:
    """Normaliza una frase para detectar repeticiones."""

    return re.sub(
        r"\W+",
        " ",
        text.casefold(),
        flags=re.UNICODE,
    ).strip()


def sentence_query_overlap(
    sentence: str,
    query: str,
) -> float:
    """Calcula cuánto vocabulario comparten pregunta y frase."""

    sentence_words = {
        word
        for word in re.findall(
            r"\b[\wáéíóúüñ]+\b",
            sentence.casefold(),
            flags=re.UNICODE,
        )
        if len(word) >= 3
    }

    query_words = {
        word
        for word in re.findall(
            r"\b[\wáéíóúüñ]+\b",
            query.casefold(),
            flags=re.UNICODE,
        )
        if len(word) >= 3
    }

    if not query_words:
        return 0.0

    return len(
        sentence_words.intersection(query_words)
    ) / len(query_words)


def build_extractive_answer(
    query: str,
    selected_chunks,
    maximum_sentences: int,
) -> dict:
    """
    Construye una respuesta básica utilizando frases de las fuentes.

    No inventa contenido ni llama a un modelo.
    """

    candidates: list[ExtractiveSentence] = []

    for source_number, result in enumerate(
        selected_chunks,
        start=1,
    ):
        sentences = split_into_sentences(
            result.chunk.content
        )

        for sentence in sentences:
            overlap = sentence_query_overlap(
                sentence,
                query,
            )

            sentence_score = (
                result.combined_score * 0.80
                + overlap * 0.20
            )

            candidates.append(
                ExtractiveSentence(
                    text=sentence,
                    source_number=source_number,
                    score=sentence_score,
                )
            )

    candidates.sort(
        key=lambda candidate: candidate.score,
        reverse=True,
    )

    selected_sentences: list[ExtractiveSentence] = []
    normalized_sentences: set[str] = set()

    for candidate in candidates:
        normalized = normalize_sentence(
            candidate.text
        )

        if normalized in normalized_sentences:
            continue

        selected_sentences.append(candidate)
        normalized_sentences.add(normalized)

        if len(selected_sentences) >= maximum_sentences:
            break

    if not selected_sentences:
        return {
            "answer": (
                "No se encontró información suficiente "
                "para construir una respuesta."
            ),
            "sentence_count": 0,
        }

    answer_parts = [
        (
            f"{candidate.text} "
            f"[FUENTE {candidate.source_number}]"
        )
        for candidate in selected_sentences
    ]

    return {
        "answer": "\n\n".join(answer_parts),
        "sentence_count": len(selected_sentences),
    }


def build_model_messages(
    query: str,
    context: str,
    instructions: str,
) -> dict:
    """
    Prepara los mensajes que utilizará un futuro proveedor de IA.
    """

    system_message = (
        "Eres el asistente académico de UniCore. "
        f"{instructions} "
        "Distingue claramente entre hechos presentes en las "
        "fuentes e interpretaciones. Responde en español."
    )

    user_message = (
        f"Pregunta del estudiante:\n{query}\n\n"
        f"Contexto recuperado:\n{context}"
    )

    return {
        "system": system_message,
        "user": user_message,
    }


def register_rag_answer_tools(mcp) -> None:
    """Registra las tools de generación de respuestas RAG."""

    @mcp.tool()
    def answer_with_rag(
        query: str,
        subject_id: int | None = None,
        mode: str = "extractive",
        maximum_sources: int = 5,
        maximum_context_characters: int = 6000,
        maximum_sentences: int = 5,
        minimum_score: float = 0.20,
        semantic_weight: float = 0.75,
        redundancy_threshold: float = 0.80,
    ) -> dict:
        """
        Genera una respuesta RAG en modo local o prepara el prompt.

        Modos disponibles:
        - extractive: crea una respuesta gratuita desde las fuentes.
        - preview: muestra el prompt para un futuro modelo.
        """

        clean_query = query.strip()
        clean_mode = mode.strip().casefold()

        if not clean_query:
            return {
                "ok": False,
                "error": "La pregunta no puede estar vacía",
            }

        if clean_mode not in {
            "extractive",
            "preview",
        }:
            return {
                "ok": False,
                "error": (
                    "mode debe ser 'extractive' o 'preview'"
                ),
            }

        if maximum_sources < 1 or maximum_sources > 20:
            return {
                "ok": False,
                "error": (
                    "maximum_sources debe estar entre 1 y 20"
                ),
            }

        if maximum_sentences < 1 or maximum_sentences > 15:
            return {
                "ok": False,
                "error": (
                    "maximum_sentences debe estar entre 1 y 15"
                ),
            }

        try:
            ranked_chunks = retrieve_ranked_chunks(
                query=clean_query,
                subject_id=subject_id,
                semantic_weight=semantic_weight,
            )
        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo recuperar el contexto RAG"
                ),
                "technical_detail": str(error),
            }

        selected_chunks = select_context_chunks(
            ranked_chunks=ranked_chunks,
            minimum_score=minimum_score,
            maximum_sources=maximum_sources,
            maximum_context_characters=(
                maximum_context_characters
            ),
            redundancy_threshold=redundancy_threshold,
        )

        evidence = calculate_evidence_status(
            selected_chunks
        )

        context = build_context_text(
            selected_chunks
        )

        instructions = (
            "Utiliza únicamente el contexto proporcionado. "
            "Cita las afirmaciones mediante [FUENTE 1], "
            "[FUENTE 2], etc. No inventes información. "
            "Cuando el contexto no sea suficiente, indícalo."
        )

        sources = [
            {
                "source_number": source_number,
                "document_id": result.document.id,
                "document_title": result.document.title,
                "chunk_id": result.chunk.id,
                "chunk_index": result.chunk.chunk_index,
                "source_label": result.chunk.source_label,
                "score": round(
                    result.combined_score,
                    6,
                ),
            }
            for source_number, result in enumerate(
                selected_chunks,
                start=1,
            )
        ]

        messages = build_model_messages(
            query=clean_query,
            context=context,
            instructions=instructions,
        )

        if clean_mode == "preview":
            return {
                "ok": True,
                "mode": "preview",
                "query": clean_query,
                "evidence": evidence,
                "source_count": len(sources),
                "context_characters": len(context),
                "messages_for_model": messages,
                "sources": sources,
                "model_called": False,
                "estimated_api_cost": 0,
            }

        if not evidence["sufficient"]:
            return {
                "ok": True,
                "mode": "extractive",
                "query": clean_query,
                "answer": (
                    "No hay evidencia suficientemente relevante "
                    "en los documentos para responder con seguridad."
                ),
                "evidence": evidence,
                "source_count": len(sources),
                "sources": sources,
                "model_called": False,
                "estimated_api_cost": 0,
            }

        extractive_result = build_extractive_answer(
            query=clean_query,
            selected_chunks=selected_chunks,
            maximum_sentences=maximum_sentences,
        )

        return {
            "ok": True,
            "mode": "extractive",
            "query": clean_query,
            "answer": extractive_result["answer"],
            "answer_sentence_count": (
                extractive_result["sentence_count"]
            ),
            "evidence": evidence,
            "source_count": len(sources),
            "context_characters": len(context),
            "sources": sources,
            "model_called": False,
            "estimated_api_cost": 0,
            "notice": (
                "Respuesta extractiva creada directamente desde "
                "las fuentes. Todavía no se utilizó un modelo "
                "generativo."
            ),
        }