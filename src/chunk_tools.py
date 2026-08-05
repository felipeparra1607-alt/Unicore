import re

from sqlalchemy import delete, select

from src.database.connection import SessionLocal
from src.database.models import Document, DocumentChunk
from src.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    cosine_similarity,
    create_embedding,
    embedding_from_json,
    embedding_to_json,
)
from src.hybrid_chunking import create_hybrid_semantic_chunks


def chunk_to_dict(chunk: DocumentChunk) -> dict:
    """Convierte un chunk de la base de datos en un diccionario."""

    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "content_length": len(chunk.content),
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "source_label": chunk.source_label,
        "chunking_strategy": chunk.chunking_strategy,
        "embedding_model": chunk.embedding_model,
        "has_embedding": bool(chunk.embedding_json),
    }


def document_summary(document: Document) -> dict:
    """Devuelve los datos principales de un documento."""

    return {
        "id": document.id,
        "title": document.title,
        "file_path": document.file_path,
        "file_type": document.file_type,
        "document_type": document.document_type,
        "subject_id": document.subject_id,
    }


def tokenize_for_lexical_search(text: str) -> set[str]:
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
    Calcula una puntuación léxica sencilla.

    Combina coincidencia de palabras y coincidencia de frase completa.
    """

    query_words = tokenize_for_lexical_search(query)

    if not query_words:
        return 0.0

    content_words = tokenize_for_lexical_search(content)

    matched_words = query_words.intersection(content_words)

    word_score = len(matched_words) / len(query_words)

    phrase_bonus = (
        0.25
        if query.casefold() in content.casefold()
        else 0.0
    )

    return min(1.0, word_score + phrase_bonus)


def create_result_snippet(
    content: str,
    query: str,
    maximum_characters: int = 600,
) -> str:
    """Crea un fragmento legible alrededor de una coincidencia."""

    if len(content) <= maximum_characters:
        return content

    normalized_content = content.casefold()
    normalized_query = query.casefold()
    position = normalized_content.find(normalized_query)

    if position == -1:
        return content[:maximum_characters].strip()

    half_window = maximum_characters // 2
    start = max(0, position - half_window)
    end = min(
        len(content),
        start + maximum_characters,
    )

    return content[start:end].strip()


def generate_chunks_for_document(
    document_id: int,
    semantic_threshold: float = 0.48,
    min_chunk_characters: int = 350,
    max_chunk_characters: int = 1800,
) -> dict:
    """
    Lógica interna para regenerar los chunks de un documento.
    """

    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "ok": False,
                "error": "Documento no encontrado",
            }

        if not document.extracted_text:
            return {
                "ok": False,
                "error": (
                    "El documento todavía no tiene texto extraído"
                ),
            }

        document_text = document.extracted_text
        document_data = document_summary(document)

    try:
        generated_chunks = create_hybrid_semantic_chunks(
            text=document_text,
            semantic_threshold=semantic_threshold,
            min_chunk_characters=min_chunk_characters,
            max_chunk_characters=max_chunk_characters,
        )
    except ValueError as error:
        return {
            "ok": False,
            "error": str(error),
        }
    except Exception as error:
        return {
            "ok": False,
            "error": "No se pudieron generar los chunks",
            "technical_detail": str(error),
        }

    if not generated_chunks:
        return {
            "ok": False,
            "error": "No se generó ningún chunk",
        }

    with SessionLocal() as session:
        session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            )
        )

        chunk_records: list[DocumentChunk] = []

        for generated_chunk in generated_chunks:
            record = DocumentChunk(
                document_id=document_id,
                chunk_index=generated_chunk.index,
                content=generated_chunk.content,
                char_start=generated_chunk.char_start,
                char_end=generated_chunk.char_end,
                source_label=generated_chunk.source_label,
                chunking_strategy="hybrid_semantic",
                embedding_model=DEFAULT_EMBEDDING_MODEL,
                embedding_json=embedding_to_json(
                    generated_chunk.embedding
                ),
            )

            session.add(record)
            chunk_records.append(record)

        session.commit()

        for record in chunk_records:
            session.refresh(record)

        return {
            "ok": True,
            "document": document_data,
            "chunk_count": len(chunk_records),
            "strategy": "hybrid_semantic",
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "settings": {
                "semantic_threshold": semantic_threshold,
                "min_chunk_characters": min_chunk_characters,
                "max_chunk_characters": max_chunk_characters,
            },
            "chunks": [
                chunk_to_dict(record)
                for record in chunk_records
            ],
        }


def register_chunk_tools(mcp) -> None:
    """
    Registra en el servidor MCP todas las tools de chunks y búsqueda.
    """

    @mcp.tool()
    def generate_document_chunks(
        document_id: int,
        semantic_threshold: float = 0.48,
        min_chunk_characters: int = 350,
        max_chunk_characters: int = 1800,
    ) -> dict:
        """
        Regenera los chunks híbridos semánticos de un documento.

        También crea y almacena el embedding de cada chunk.
        """

        return generate_chunks_for_document(
            document_id=document_id,
            semantic_threshold=semantic_threshold,
            min_chunk_characters=min_chunk_characters,
            max_chunk_characters=max_chunk_characters,
        )

    @mcp.tool()
    def generate_pending_chunks(
        subject_id: int | None = None,
        limit: int = 50,
        semantic_threshold: float = 0.48,
        min_chunk_characters: int = 350,
        max_chunk_characters: int = 1800,
    ) -> dict:
        """
        Genera chunks para documentos con texto que aún no tienen chunks.
        """

        if limit < 1 or limit > 500:
            return {
                "ok": False,
                "error": "El límite debe estar entre 1 y 500",
            }

        with SessionLocal() as session:
            statement = select(Document).where(
                Document.extracted_text.is_not(None)
            )

            if subject_id is not None:
                statement = statement.where(
                    Document.subject_id == subject_id
                )

            documents = session.scalars(
                statement.order_by(Document.id)
            ).all()

            pending_document_ids = [
                document.id
                for document in documents
                if not document.chunks
            ][:limit]

        successful: list[dict] = []
        failed: list[dict] = []

        for pending_document_id in pending_document_ids:
            result = generate_chunks_for_document(
                document_id=pending_document_id,
                semantic_threshold=semantic_threshold,
                min_chunk_characters=min_chunk_characters,
                max_chunk_characters=max_chunk_characters,
            )

            if result.get("ok"):
                successful.append({
                    "document_id": pending_document_id,
                    "chunk_count": result["chunk_count"],
                })
            else:
                failed.append({
                    "document_id": pending_document_id,
                    "error": result.get("error"),
                    "technical_detail": result.get(
                        "technical_detail"
                    ),
                })

        return {
            "ok": True,
            "pending_documents_found": len(
                pending_document_ids
            ),
            "successful_count": len(successful),
            "failed_count": len(failed),
            "successful": successful,
            "failed": failed,
        }

    @mcp.tool()
    def list_document_chunks(
        document_id: int,
        include_content: bool = True,
    ) -> dict:
        """Lista todos los chunks de un documento."""

        with SessionLocal() as session:
            document = session.get(Document, document_id)

            if document is None:
                return {
                    "ok": False,
                    "error": "Documento no encontrado",
                }

            chunks = session.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id
                )
                .order_by(DocumentChunk.chunk_index)
            ).all()

            chunk_results: list[dict] = []

            for chunk in chunks:
                chunk_data = chunk_to_dict(chunk)

                if not include_content:
                    chunk_data.pop("content", None)

                chunk_results.append(chunk_data)

            return {
                "ok": True,
                "document": document_summary(document),
                "chunk_count": len(chunk_results),
                "chunks": chunk_results,
            }

    @mcp.tool()
    def get_document_chunk(chunk_id: int) -> dict:
        """Devuelve un chunk concreto y su documento original."""

        with SessionLocal() as session:
            chunk = session.get(DocumentChunk, chunk_id)

            if chunk is None:
                return {
                    "ok": False,
                    "error": "Chunk no encontrado",
                }

            document = session.get(
                Document,
                chunk.document_id,
            )

            return {
                "ok": True,
                "chunk": chunk_to_dict(chunk),
                "document": (
                    document_summary(document)
                    if document is not None
                    else None
                ),
            }

    @mcp.tool()
    def delete_document_chunks(document_id: int) -> dict:
        """
        Elimina todos los chunks de un documento.

        No elimina el documento ni su texto extraído.
        """

        with SessionLocal() as session:
            document = session.get(Document, document_id)

            if document is None:
                return {
                    "ok": False,
                    "error": "Documento no encontrado",
                }

            chunks = session.scalars(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == document_id
                )
            ).all()

            deleted_count = len(chunks)

            session.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == document_id
                )
            )

            session.commit()

            return {
                "ok": True,
                "document": document_summary(document),
                "deleted_chunk_count": deleted_count,
                "document_deleted": False,
                "extracted_text_deleted": False,
            }

    @mcp.tool()
    def semantic_search(
        query: str,
        subject_id: int | None = None,
        max_results: int = 10,
        minimum_score: float = 0.20,
    ) -> dict:
        """
        Busca chunks por similitud semántica con la pregunta.
        """

        clean_query = query.strip()

        if not clean_query:
            return {
                "ok": False,
                "error": "La búsqueda no puede estar vacía",
            }

        if max_results < 1 or max_results > 50:
            return {
                "ok": False,
                "error": "max_results debe estar entre 1 y 50",
            }

        if minimum_score < -1 or minimum_score > 1:
            return {
                "ok": False,
                "error": (
                    "minimum_score debe estar entre -1 y 1"
                ),
            }

        try:
            query_embedding = create_embedding(clean_query)
        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo crear el embedding de la búsqueda"
                ),
                "technical_detail": str(error),
            }

        with SessionLocal() as session:
            statement = (
                select(DocumentChunk, Document)
                .join(
                    Document,
                    Document.id
                    == DocumentChunk.document_id,
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

            ranked_results: list[dict] = []

            for chunk, document in rows:
                chunk_embedding = embedding_from_json(
                    chunk.embedding_json
                )

                score = cosine_similarity(
                    query_embedding,
                    chunk_embedding,
                )

                if score < minimum_score:
                    continue

                ranked_results.append({
                    "score": round(score, 6),
                    "document": document_summary(document),
                    "chunk": chunk_to_dict(chunk),
                    "snippet": create_result_snippet(
                        chunk.content,
                        clean_query,
                    ),
                })

            ranked_results.sort(
                key=lambda result: result["score"],
                reverse=True,
            )

            selected_results = ranked_results[:max_results]

            return {
                "ok": True,
                "query": clean_query,
                "search_type": "semantic",
                "result_count": len(selected_results),
                "minimum_score": minimum_score,
                "results": selected_results,
            }

    @mcp.tool()
    def hybrid_search(
        query: str,
        subject_id: int | None = None,
        max_results: int = 10,
        minimum_score: float = 0.15,
        semantic_weight: float = 0.75,
    ) -> dict:
        """
        Combina búsqueda semántica y coincidencia de palabras.

        Por defecto:
        75 % significado semántico.
        25 % coincidencia léxica.
        """

        clean_query = query.strip()

        if not clean_query:
            return {
                "ok": False,
                "error": "La búsqueda no puede estar vacía",
            }

        if max_results < 1 or max_results > 50:
            return {
                "ok": False,
                "error": "max_results debe estar entre 1 y 50",
            }

        if semantic_weight < 0 or semantic_weight > 1:
            return {
                "ok": False,
                "error": (
                    "semantic_weight debe estar entre 0 y 1"
                ),
            }

        if minimum_score < 0 or minimum_score > 1:
            return {
                "ok": False,
                "error": (
                    "minimum_score debe estar entre 0 y 1"
                ),
            }

        lexical_weight = 1.0 - semantic_weight

        try:
            query_embedding = create_embedding(clean_query)
        except Exception as error:
            return {
                "ok": False,
                "error": (
                    "No se pudo crear el embedding de la búsqueda"
                ),
                "technical_detail": str(error),
            }

        with SessionLocal() as session:
            statement = (
                select(DocumentChunk, Document)
                .join(
                    Document,
                    Document.id
                    == DocumentChunk.document_id,
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

            ranked_results: list[dict] = []

            for chunk, document in rows:
                chunk_embedding = embedding_from_json(
                    chunk.embedding_json
                )

                semantic_score = max(
                    0.0,
                    cosine_similarity(
                        query_embedding,
                        chunk_embedding,
                    ),
                )

                lexical_score = calculate_lexical_score(
                    clean_query,
                    chunk.content,
                )

                combined_score = (
                    semantic_score * semantic_weight
                    + lexical_score * lexical_weight
                )

                if combined_score < minimum_score:
                    continue

                ranked_results.append({
                    "score": round(combined_score, 6),
                    "semantic_score": round(
                        semantic_score,
                        6,
                    ),
                    "lexical_score": round(
                        lexical_score,
                        6,
                    ),
                    "document": document_summary(document),
                    "chunk": chunk_to_dict(chunk),
                    "snippet": create_result_snippet(
                        chunk.content,
                        clean_query,
                    ),
                })

            ranked_results.sort(
                key=lambda result: result["score"],
                reverse=True,
            )

            selected_results = ranked_results[:max_results]

            return {
                "ok": True,
                "query": clean_query,
                "search_type": "hybrid",
                "result_count": len(selected_results),
                "weights": {
                    "semantic": semantic_weight,
                    "lexical": lexical_weight,
                },
                "minimum_score": minimum_score,
                "results": selected_results,
            }