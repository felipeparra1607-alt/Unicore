from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    Document,
    Professor,
    ProfessorPreference,
    RubricCriterion,
    Subject,
)
from src.model_answer_tools import build_sources_summary
from src.rag_tools import build_context_text, retrieve_ranked_chunks, select_context_chunks
from src.v11_services import hierarchical_retrieval, student_model


PROMPT_RAG_TOP_K = 4
PROMPT_CONTEXT_CHARACTERS = 4200


def _compact(value: str | None, limit: int) -> str | None:
    clean = " ".join((value or "").split())
    if not clean:
        return None
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def build_academic_prompt(
    *,
    objective: str,
    subject_id: int | None = None,
    task_id: int | None = None,
    document_id: int | None = None,
    maximum_sources: int = PROMPT_RAG_TOP_K,
    maximum_context_characters: int = PROMPT_CONTEXT_CHARACTERS,
    session_factory=SessionLocal,
    retriever: Callable[..., list] = retrieve_ranked_chunks,
    include_professor: bool = True,
    include_rubric: bool = True,
    include_academic_memory: bool = False,
    include_improvements: bool = False,
    include_strengths: bool = False,
) -> dict[str, Any]:
    """Construye un prompt académico selectivo sin llamar a un modelo."""

    clean_objective = _compact(objective, 1200)
    if not clean_objective:
        return {"ok": False, "error": "Describe qué debe conseguir el prompt"}
    if maximum_sources < 1 or maximum_sources > PROMPT_RAG_TOP_K:
        return {"ok": False, "error": f"maximum_sources debe estar entre 1 y {PROMPT_RAG_TOP_K}"}
    if maximum_context_characters < 500 or maximum_context_characters > PROMPT_CONTEXT_CHARACTERS:
        return {
            "ok": False,
            "error": f"maximum_context_characters debe estar entre 500 y {PROMPT_CONTEXT_CHARACTERS}",
        }

    with session_factory() as session:
        task = session.get(AcademicTask, task_id) if task_id is not None else None
        if task_id is not None and task is None:
            return {"ok": False, "error": "La tarea seleccionada no existe"}
        effective_subject_id = subject_id if subject_id is not None else (task.subject_id if task else None)
        if task and subject_id is not None and task.subject_id not in {None, subject_id}:
            return {"ok": False, "error": "La tarea no pertenece a la asignatura seleccionada"}

        document = session.get(Document, document_id) if document_id is not None else None
        if document_id is not None and document is None:
            return {"ok": False, "error": "El material seleccionado no existe"}
        if document and effective_subject_id is not None and document.subject_id != effective_subject_id:
            return {"ok": False, "error": "El material no pertenece a la asignatura seleccionada"}
        if effective_subject_id is None and document is not None:
            effective_subject_id = document.subject_id

        subject = session.get(Subject, effective_subject_id) if effective_subject_id is not None else None
        if effective_subject_id is not None and subject is None:
            return {"ok": False, "error": "La asignatura seleccionada no existe"}

        professors = []
        preferences = []
        rubric = []
        if subject is not None and (include_professor or include_rubric):
            professors = list(session.scalars(select(Professor).where(Professor.subject_id == subject.id)))
            preferences = list(
                session.scalars(
                    select(ProfessorPreference)
                    .where(ProfessorPreference.subject_id == subject.id)
                    .order_by(ProfessorPreference.importance.desc(), ProfessorPreference.confidence.desc())
                    .limit(6)
                )
            )
            rubric = list(
                session.scalars(
                    select(RubricCriterion)
                    .where(RubricCriterion.subject_id == subject.id)
                    .order_by(RubricCriterion.weight_percentage.desc().nullslast(), RubricCriterion.id)
                    .limit(6)
                )
            )
            if not include_professor:
                professors = []
                preferences = []
            if not include_rubric:
                rubric = []

        subject_name = subject.name if subject is not None else None
        professor_names = [item.name for item in professors]
        task_data = None
        if task is not None:
            task_data = {
                "title": task.title,
                "type": task.task_type,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "description": _compact(task.description, 1800),
                "notes": _compact(task.notes, 900),
            }
        preference_lines = [_compact(item.preference, 360) for item in preferences]
        preference_lines = [item for item in preference_lines if item]
        rubric_lines = []
        for item in rubric:
            detail = _compact(item.description or item.notes, 420)
            weight = f" ({item.weight_percentage:g}%)" if item.weight_percentage is not None else ""
            rubric_lines.append(f"{item.title}{weight}" + (f": {detail}" if detail else ""))

    selected_chunks = []
    historical_source_count = 0
    if effective_subject_id is not None:
        if include_academic_memory and document_id is None:
            hierarchy = hierarchical_retrieval(
                query=clean_objective,
                subject_id=effective_subject_id,
                include_global=True,
                retriever=retriever,
            )
            selected_chunks = [*hierarchy["current"], *hierarchy["historical"]]
            historical_source_count = len(hierarchy["historical"])
        else:
            ranked = retriever(
                query=clean_objective,
                subject_id=effective_subject_id,
                document_id=document_id,
                semantic_weight=0.75,
            )
            selected_chunks = select_context_chunks(
                ranked_chunks=ranked,
                minimum_score=0.20,
                maximum_sources=maximum_sources,
                maximum_context_characters=maximum_context_characters,
                redundancy_threshold=0.80,
            )

    sources = build_sources_summary(selected_chunks)
    material_context = build_context_text(selected_chunks)
    sections = [
        "ROL\nActúa como un asistente académico riguroso y orientado a la tarea.",
        f"OBJETIVO\n{clean_objective}",
    ]
    context_lines = []
    if subject_name:
        context_lines.append(f"Asignatura: {subject_name}")
    if professor_names:
        context_lines.append(f"Profesorado: {', '.join(professor_names)}")
    if document is not None:
        context_lines.append(f"Material activo: {document.title}")
    if context_lines:
        sections.append("CONTEXTO\n" + "\n".join(context_lines))
    if task_data:
        task_lines = [f"Tarea: {task_data['title']}", f"Tipo: {task_data['type']}"]
        if task_data["due_date"]:
            task_lines.append(f"Fecha de entrega: {task_data['due_date']}")
        if task_data["description"]:
            task_lines.append(f"Enunciado y requisitos: {task_data['description']}")
        if task_data["notes"]:
            task_lines.append(f"Notas relevantes: {task_data['notes']}")
        sections.append("TAREA\n" + "\n".join(task_lines))
    if preference_lines:
        sections.append(
            "CRITERIOS DEL PROFESOR\n"
            + "\n".join(f"{index}. {line}" for index, line in enumerate(preference_lines, start=1))
        )
    if rubric_lines:
        sections.append(
            "RÚBRICA RELEVANTE\n"
            + "\n".join(f"{index}. {line}" for index, line in enumerate(rubric_lines, start=1))
        )
    if material_context:
        sections.append("MATERIAL RELEVANTE\n" + material_context)
    model = student_model(subject_id=effective_subject_id, session_factory=session_factory)
    if include_improvements and model["areas_for_improvement"]:
        sections.append(
            "ÁREAS DE MEJORA ACTUALES\n"
            + "\n".join(f"- {item['dimension']}: {item['status']}" for item in model["areas_for_improvement"][:4])
        )
    if include_strengths and model["strengths"]:
        sections.append(
            "FORTALEZAS ACTUALES\n"
            + "\n".join(f"- {item['dimension']}" for item in model["strengths"][:4])
        )
    sections.append(
        "INSTRUCCIONES\n"
        "Trabaja únicamente con el contexto proporcionado. Señala cualquier dato que falte en vez de inventarlo. "
        "Prioriza claridad, precisión académica y cumplimiento explícito de los requisitos."
    )
    sections.append(
        "FORMATO DE RESPUESTA\n"
        "Entrega una respuesta directamente utilizable, bien estructurada y proporcionada al objetivo."
    )
    prompt = "\n\n".join(sections)
    return {
        "ok": True,
        "prompt": prompt,
        "sources": sources,
        "context": {
            "subject_id": effective_subject_id,
            "subject_name": subject_name,
            "task_id": task.id if task is not None else None,
            "task_title": task.title if task is not None else None,
            "document_id": document.id if document is not None else None,
            "document_title": document.title if document is not None else None,
            "professor_criteria_count": len(preference_lines),
            "rubric_criteria_count": len(rubric_lines),
        },
        "retrieval": {
            "top_k": maximum_sources,
            "source_count": len(sources),
            "context_characters": len(material_context),
            "subject_filtered": effective_subject_id is not None,
            "document_filtered": document_id is not None,
            "provider_called": False,
            "historical_source_count": historical_source_count,
        },
        "context_selection": {
            "professor": include_professor,
            "rubric": include_rubric,
            "academic_memory": include_academic_memory,
            "improvements": include_improvements,
            "strengths": include_strengths,
            "estimated_load": "Alto" if include_academic_memory and (include_professor or include_rubric) else "Medio" if any([include_professor, include_rubric, include_improvements, include_strengths]) else "Bajo",
        },
    }
