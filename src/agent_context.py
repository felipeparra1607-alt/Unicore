from __future__ import annotations

import json
import re
from typing import Any

from src.rag_tools import (
    build_context_text,
    retrieve_ranked_chunks,
    select_context_chunks,
)
from src.v11_services import hierarchical_retrieval


RAG_TOP_K = 4
RAG_CONTEXT_CHARACTERS = 4500
SUPPLEMENTAL_CONTEXT_CHARACTERS = 10500

_NO_RETRIEVAL_PATTERNS = (
    r"^(hola|buenas|vale|perfecto|de acuerdo)[.!¡¿? ]*$",
    r"^gracias(?:\s+por\s+.{1,80})?[.!¡¿? ]*$",
    r"^(expl[ií]camelo|expl[ií]came|d[ií]melo|res[uú]melo)\s+m[aá]s\s+(f[aá]cil|simple|sencill[oa]|breve)",
)
_DOCUMENT_TERMS = {
    "apunte", "apuntes", "archivo", "documento", "material", "pdf", "pptx",
    "lectura", "tema", "contenido", "diapositiva", "página", "pagina",
    "según", "segun", "texto", "profesor", "rúbrica", "rubrica", "criterio",
    "teoría", "teoria", "concepto", "define", "explica", "diferencia",
}

_GLOBAL_MEMORY_PATTERNS = (
    r"otras? asignaturas?",
    r"asignaturas? anteriores?",
    r"conocimientos? (?:previos?|anteriores?)",
    r"academic memory",
    r"estudi[ée] antes",
    r"relaciona(?:r|lo)? con (?:algo|cosas) (?:anterior|previo)",
)


def requests_global_academic_memory(message: str) -> bool:
    clean = " ".join(message.casefold().split())
    return any(re.search(pattern, clean) for pattern in _GLOBAL_MEMORY_PATTERNS)


def needs_document_retrieval(message: str, document_id: int | None = None) -> bool:
    clean = " ".join(message.casefold().split())
    if any(re.search(pattern, clean) for pattern in _NO_RETRIEVAL_PATTERNS):
        return False
    if document_id is not None:
        return True
    words = set(re.findall(r"\b[\wáéíóúüñ]+\b", clean, flags=re.UNICODE))
    return bool(words.intersection(_DOCUMENT_TERMS))


def _safe_work_context(work_context: Any) -> dict:
    if not isinstance(work_context, dict):
        return {}
    allowed = {
        "action", "subject", "due_date", "progress_percentage",
        "task_description", "task_notes", "duration_minutes",
    }
    result: dict[str, Any] = {}
    for key in allowed:
        value = work_context.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[key] = value
    return result


def build_selective_agent_context(
    *,
    message: str,
    memory: dict,
    subject_id: int | None = None,
    document_id: int | None = None,
    work_context: Any = None,
) -> dict:
    blocks: list[str] = []
    summary = str(memory.get("summary") or "").strip()
    if summary:
        blocks.append("MEMORIA COMPACTA:\n" + summary)

    recent_messages = memory.get("recent_messages") or []
    if recent_messages:
        lines = []
        for item in recent_messages:
            role = "Usuario" if item.get("role") == "user" else "UniCore"
            lines.append(f"{role}: {str(item.get('content') or '').strip()}")
        blocks.append("VENTANA RECIENTE:\n" + "\n".join(lines))

    safe_work = _safe_work_context(work_context)
    if safe_work:
        blocks.append(
            "SESIÓN DE TRABAJO ACTIVA:\n"
            + json.dumps(safe_work, ensure_ascii=False, separators=(",", ":"))
        )

    sources: list[dict] = []
    retrieval_used = needs_document_retrieval(message, document_id)
    context_characters = 0
    global_requested = requests_global_academic_memory(message)
    if retrieval_used:
        if global_requested and subject_id is not None and document_id is None:
            hierarchy = hierarchical_retrieval(
                query=message,
                subject_id=subject_id,
                include_global=True,
            )
            selected = [*hierarchy["current"], *hierarchy["historical"]]
        else:
            ranked = retrieve_ranked_chunks(
                query=message,
                subject_id=subject_id,
                document_id=document_id,
                semantic_weight=0.75,
            )
            selected = select_context_chunks(
                ranked_chunks=ranked,
                minimum_score=0.20,
                maximum_sources=RAG_TOP_K,
                maximum_context_characters=RAG_CONTEXT_CHARACTERS,
                redundancy_threshold=0.80,
            )
        if selected:
            rag_context = build_context_text(selected)
            context_characters = len(rag_context)
            blocks.append(
                "FUENTES DOCUMENTALES RECUPERADAS. Úsalas solo si responden a la pregunta "
                "y cita [FUENTE N]:\n" + rag_context
            )
            sources = [
                {
                    "source_number": index,
                    "document_id": item.document.id,
                    "document_title": item.document.title,
                    "source_label": item.chunk.source_label,
                }
                for index, item in enumerate(selected, start=1)
            ]

    context = "\n\n".join(blocks)
    if len(context) > SUPPLEMENTAL_CONTEXT_CHARACTERS:
        context = context[-SUPPLEMENTAL_CONTEXT_CHARACTERS:]
    return {
        "context": context,
        "sources": sources,
        "retrieval": {
            "used": retrieval_used,
            "top_k": RAG_TOP_K,
            "source_count": len(sources),
            "context_characters": context_characters,
            "subject_filtered": subject_id is not None,
            "document_filtered": document_id is not None,
            "global_requested": global_requested,
            "historical_source_count": sum(
                1 for item in selected
                if subject_id is not None and item.document.subject_id != subject_id
            ) if retrieval_used else 0,
        },
    }
