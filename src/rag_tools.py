import re
from dataclasses import dataclass

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import Document, DocumentChunk
from src.embeddings import (
    cosine_similarity,
    create_embedding,
    embedding_from_json,
)


@dataclass
class RankedChunk:
    """Representa un chunk recuperado y puntuado."""

    chunk: DocumentChunk
    document: Document
    semantic_score: float
    lexical_score: float
    combined_score: float


def document_to_source_dict(document: Document) -> dict:
    """Devuelve los datos necesarios para identificar una fuente."""

    return {
        "document_id": document.id,
        "title": document.title,
        "file_path": document.file_path,
        "file_type": document.file_type,
        "document_type": document.document_type,
        "subject_id": document.subject_id,
    }


def chunk_to_source_dict(chunk: DocumentChunk) -> dict:
    """Devuelve la localización de un chunk dentro del documento."""

    return {
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "source_label": chunk.source_label,
        "content_length": len(chunk.content),
    }


def tokenize(text: str) -> set[str]:
    """Convierte un texto en palabras normalizadas."""

    return {
        word
        for word in re.findall(
            r"\b[\wáéíóúüñ]+\b",
            text.casefold(),
            flags=re.UNICODE,
        )
        if len(word) >= 2
    }


def calculate_lexical_score(
    query: str,
    content: str,
) -> float:
    """
    Calcula coincidencia de palabras y frase exacta.

    Esta es una puntuación léxica sencilla.
    Más adelante podremos sustituirla por BM25 real.
    """

    query_words = tokenize(query)

    if not query_words:
        return 0.0

    content_words = tokenize(content)
    matched_words = query_words.intersection(content_words)

    word_score = len(matched_words) / len(query_words)

    phrase_bonus = (
        0.25
        if query.casefold() in content.casefold()
        else 0.0
    )

    return min(1.0, word_score + phrase_bonus)


def normalize_semantic_score(score: float) -> float:
    """
    Convierte una similitud coseno al intervalo de 0 a 1.

    Los valores negativos se tratan como ausencia de relación.
    """

    return max(0.0, min(1.0, score))


def retrieve_ranked_chunks(
    query: str,
    subject_id: int | None,
    semantic_weight: float,
) -> list[RankedChunk]:
    """Recupera y ordena todos los chunks compatibles."""

    query_embedding = create_embedding(query)
    lexical_weight = 1.0 - semantic_weight

    with SessionLocal() as session:
        statement = (
            select(DocumentChunk, Document)
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .where(
                DocumentChunk.embedding_json.is_not(None)
            )
        )

        if subject_id is not None:
            statement = statement.where(
                Document.subject_id == subject_id
            )

        rows = session.execute(statement).all()

        ranked_chunks: list[RankedChunk] = []

        for chunk, document in rows:
            stored_embedding = embedding_from_json(
                chunk.embedding_json
            )

            semantic_score = normalize_semantic_score(
                cosine_similarity(
                    query_embedding,
                    stored_embedding,
                )
            )

            lexical_score = calculate_lexical_score(
                query,
                chunk.content,
            )

            combined_score = (
                semantic_score * semantic_weight
                + lexical_score * lexical_weight
            )

            ranked_chunks.append(
                RankedChunk(
                    chunk=chunk,
                    document=document,
                    semantic_score=semantic_score,
                    lexical_score=lexical_score,
                    combined_score=combined_score,
                )
            )

        ranked_chunks.sort(
            key=lambda item: item.combined_score,
            reverse=True,
        )

        return ranked_chunks


def text_similarity_ratio(
    first_text: str,
    second_text: str,
) -> float:
    """
    Estima cuánto vocabulario comparten dos chunks.

    Sirve para reducir resultados redundantes.
    """

    first_words = tokenize(first_text)
    second_words = tokenize(second_text)

    if not first_words or not second_words:
        return 0.0

    intersection = first_words.intersection(second_words)
    smaller_set_size = min(
        len(first_words),
        len(second_words),
    )

    return len(intersection) / smaller_set_size


def chunks_are_redundant(
    candidate: RankedChunk,
    selected: RankedChunk,
    redundancy_threshold: float,
) -> bool:
    """Comprueba si dos chunks aportarían información repetida."""

    same_document = (
        candidate.document.id == selected.document.id
    )

    adjacent_chunks = (
        same_document
        and abs(
            candidate.chunk.chunk_index
            - selected.chunk.chunk_index
        )
        <= 1
    )

    vocabulary_overlap = text_similarity_ratio(
        candidate.chunk.content,
        selected.chunk.content,
    )

    highly_similar_text = (
        vocabulary_overlap >= redundancy_threshold
    )

    return adjacent_chunks and highly_similar_text


def select_context_chunks(
    ranked_chunks: list[RankedChunk],
    minimum_score: float,
    maximum_sources: int,
    maximum_context_characters: int,
    redundancy_threshold: float,
) -> list[RankedChunk]:
    """
    Selecciona chunks relevantes respetando límites y redundancia.
    """

    selected: list[RankedChunk] = []
    used_characters = 0

    for candidate in ranked_chunks:
        if candidate.combined_score < minimum_score:
            continue

        redundant = any(
            chunks_are_redundant(
                candidate,
                existing,
                redundancy_threshold,
            )
            for existing in selected
        )

        if redundant:
            continue

        source_overhead = 160
        required_characters = (
            len(candidate.chunk.content)
            + source_overhead
        )

        if (
            selected
            and used_characters + required_characters
            > maximum_context_characters
        ):
            continue

        selected.append(candidate)
        used_characters += required_characters

        if len(selected) >= maximum_sources:
            break

    return selected


def build_context_text(
    selected_chunks: list[RankedChunk],
) -> str:
    """Construye el contexto que recibirá el futuro modelo."""

    context_blocks: list[str] = []

    for source_number, result in enumerate(
        selected_chunks,
        start=1,
    ):
        source_location = (
            result.chunk.source_label
            or f"fragmento {result.chunk.chunk_index}"
        )

        header = (
            f"[FUENTE {source_number}]\n"
            f"Documento: {result.document.title}\n"
            f"Documento ID: {result.document.id}\n"
            f"Chunk ID: {result.chunk.id}\n"
            f"Ubicación: {source_location}\n"
            f"Relevancia: {result.combined_score:.4f}"
        )

        context_blocks.append(
            f"{header}\n\n"
            f"{result.chunk.content.strip()}"
        )

    return "\n\n---\n\n".join(context_blocks)


def calculate_evidence_status(
    selected_chunks: list[RankedChunk],
) -> dict:
    """
    Estima si existe evidencia suficiente para responder.

    No garantiza que la respuesta sea correcta. Es una señal
    orientativa para decidir si debe responderse con cautela.
    """

    if not selected_chunks:
        return {
            "status": "insufficient",
            "sufficient": False,
            "reason": "No se encontraron fuentes relevantes",
            "top_score": 0.0,
        }

    top_score = selected_chunks[0].combined_score

    if top_score >= 0.65:
        return {
            "status": "strong",
            "sufficient": True,
            "reason": "Existe al menos una fuente muy relevante",
            "top_score": round(top_score, 6),
        }

    if top_score >= 0.40:
        return {
            "status": "moderate",
            "sufficient": True,
            "reason": (
                "Existen fuentes relacionadas, pero la respuesta "
                "debería formularse con precaución"
            ),
            "top_score": round(top_score, 6),
        }

    return {
        "status": "weak",
        "sufficient": False,
        "reason": (
            "Las fuentes encontradas tienen una relevancia baja"
        ),
        "top_score": round(top_score, 6),
    }


def register_rag_tools(mcp) -> None:
    """Registra las tools del primer sistema RAG."""

    @mcp.tool()
    def check_rag_readiness(
        subject_id: int | None = None,
    ) -> dict:
        """
        Comprueba cuántos documentos y chunks están preparados para RAG.
        """

        with SessionLocal() as session:
            document_statement = select(Document)

            if subject_id is not None:
                document_statement = document_statement.where(
                    Document.subject_id == subject_id
                )

            documents = session.scalars(
                document_statement.order_by(Document.id)
            ).all()

            document_ids = [
                document.id
                for document in documents
            ]

            if not document_ids:
                return {
                    "ok": True,
                    "ready": False,
                    "subject_id": subject_id,
                    "document_count": 0,
                    "documents_with_text": 0,
                    "documents_with_chunks": 0,
                    "chunk_count": 0,
                    "chunks_with_embeddings": 0,
                    "reason": "No hay documentos disponibles",
                }

            chunks = session.scalars(
                select(DocumentChunk).where(
                    DocumentChunk.document_id.in_(
                        document_ids
                    )
                )
            ).all()

            documents_with_text = sum(
                1
                for document in documents
                if document.extracted_text
            )

            document_ids_with_chunks = {
                chunk.document_id
                for chunk in chunks
            }

            chunks_with_embeddings = sum(
                1
                for chunk in chunks
                if chunk.embedding_json
            )

            ready = (
                documents_with_text > 0
                and len(chunks) > 0
                and chunks_with_embeddings == len(chunks)
            )

            return {
                "ok": True,
                "ready": ready,
                "subject_id": subject_id,
                "document_count": len(documents),
                "documents_with_text": documents_with_text,
                "documents_with_chunks": len(
                    document_ids_with_chunks
                ),
                "chunk_count": len(chunks),
                "chunks_with_embeddings": (
                    chunks_with_embeddings
                ),
                "reason": (
                    "El contenido está preparado para RAG"
                    if ready
                    else (
                        "Faltan textos, chunks o embeddings"
                    )
                ),
            }

    @mcp.tool()
    def build_rag_context(
        query: str,
        subject_id: int | None = None,
        maximum_sources: int = 5,
        maximum_context_characters: int = 6000,
        minimum_score: float = 0.20,
        semantic_weight: float = 0.75,
        redundancy_threshold: float = 0.80,
    ) -> dict:
        """
        Construye un contexto RAG relevante, limitado y citado.

        Esta tool todavía no llama a un modelo de lenguaje.
        Prepara las fuentes que deberá utilizar el modelo.
        """

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

        if minimum_score < 0 or minimum_score > 1:
            return {
                "ok": False,
                "error": (
                    "minimum_score debe estar entre 0 y 1"
                ),
            }

        if semantic_weight < 0 or semantic_weight > 1:
            return {
                "ok": False,
                "error": (
                    "semantic_weight debe estar entre 0 y 1"
                ),
            }

        if (
            redundancy_threshold < 0
            or redundancy_threshold > 1
        ):
            return {
                "ok": False,
                "error": (
                    "redundancy_threshold debe estar "
                    "entre 0 y 1"
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
                    "No se pudo realizar la recuperación RAG"
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

        context = build_context_text(selected_chunks)

        sources: list[dict] = []

        for source_number, result in enumerate(
            selected_chunks,
            start=1,
        ):
            sources.append({
                "source_number": source_number,
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
                "document": document_to_source_dict(
                    result.document
                ),
                "chunk": chunk_to_source_dict(
                    result.chunk
                ),
                "content": result.chunk.content,
            })

        instructions = (
            "Responde utilizando únicamente las fuentes "
            "proporcionadas. Cita las afirmaciones con el formato "
            "[FUENTE 1], [FUENTE 2], etc. No inventes información. "
            "Cuando las fuentes no sean suficientes, indícalo "
            "claramente."
        )

        return {
            "ok": True,
            "query": clean_query,
            "subject_id": subject_id,
            "retrieval_type": "hybrid",
            "source_count": len(sources),
            "context_characters": len(context),
            "evidence": evidence,
            "instructions_for_model": instructions,
            "context": context,
            "sources": sources,
            "settings": {
                "maximum_sources": maximum_sources,
                "maximum_context_characters": (
                    maximum_context_characters
                ),
                "minimum_score": minimum_score,
                "semantic_weight": semantic_weight,
                "lexical_weight": (
                    1.0 - semantic_weight
                ),
                "redundancy_threshold": (
                    redundancy_threshold
                ),
            },
        }

    @mcp.tool()
    def get_rag_source(
        chunk_id: int,
    ) -> dict:
        """
        Recupera una fuente completa utilizada por el sistema RAG.
        """

        with SessionLocal() as session:
            chunk = session.get(
                DocumentChunk,
                chunk_id,
            )

            if chunk is None:
                return {
                    "ok": False,
                    "error": "Fuente o chunk no encontrado",
                }

            document = session.get(
                Document,
                chunk.document_id,
            )

            if document is None:
                return {
                    "ok": False,
                    "error": (
                        "El documento original no está disponible"
                    ),
                }

            return {
                "ok": True,
                "document": document_to_source_dict(
                    document
                ),
                "chunk": chunk_to_source_dict(chunk),
                "content": chunk.content,
                "citation": {
                    "document_title": document.title,
                    "document_id": document.id,
                    "chunk_id": chunk.id,
                    "source_label": chunk.source_label,
                },
            }