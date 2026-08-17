from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.ai_config import get_ai_settings
from src.database.connection import SessionLocal
from src.database.models import (
    CurriculumItem,
    Document,
    DocumentChunk,
    StudyTopicAnalysis,
    Subject,
)
from src.providers import create_provider
from src.providers.base import GenerationRequest
from src.rag_tools import build_context_text, retrieve_ranked_chunks, select_context_chunks
from src.study_tools import extract_json_object
from src.v11_services import record_token_usage

ANALYSIS_VERSION = "study-analysis-v1"
LEVELS = {"low": "Baja", "medium": "Media", "high": "Alta"}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _material_fingerprint(subject_id: int, *, session_factory=SessionLocal) -> str:
    with session_factory() as session:
        rows = session.execute(
            select(Document.id, Document.content_hash, Document.extracted_text)
            .where(
                Document.subject_id == subject_id,
                Document.processing_status == "ready",
            )
            .order_by(Document.id)
        ).all()
    stable = "|".join(
        f"{row.id}:{row.content_hash or ''}:{len(row.extracted_text or '')}"
        for row in rows
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _validate_item(item_id: int, *, session_factory=SessionLocal) -> tuple[CurriculumItem, Subject] | tuple[None, None]:
    with session_factory() as session:
        item = session.get(CurriculumItem, item_id)
        if (
            item is None
            or item.item_type not in {"topic", "subtopic"}
            or item.source == "rejected"
            or not item.manually_locked
        ):
            return None, None
        subject = session.get(Subject, item.subject_id)
        if subject is None:
            return None, None
        session.expunge(item)
        session.expunge(subject)
        return item, subject


def _subtopic_names(item_id: int, *, session_factory=SessionLocal) -> list[str]:
    with session_factory() as session:
        return list(session.scalars(
            select(CurriculumItem.name)
            .where(
                CurriculumItem.parent_id == item_id,
                CurriculumItem.item_type == "subtopic",
                CurriculumItem.source != "rejected",
                CurriculumItem.manually_locked.is_(True),
            )
            .order_by(CurriculumItem.position, CurriculumItem.id)
        ))


def _analysis_to_dict(entry: StudyTopicAnalysis, *, current_fingerprint: str) -> dict[str, Any]:
    try:
        source_chunk_ids = json.loads(entry.source_chunk_ids_json or "[]")
    except json.JSONDecodeError:
        source_chunk_ids = []
    try:
        questions = json.loads(entry.diagnostic_questions_json or "[]")
    except json.JSONDecodeError:
        questions = []
    safe_questions = [
        {"level": str(question.get("level") or ""), "question": str(question.get("question") or "")}
        for question in questions
        if isinstance(question, dict)
    ]
    try:
        scores = json.loads(entry.diagnostic_scores_json or "[]")
    except json.JSONDecodeError:
        scores = []
    return {
        "ok": True,
        "analysis": {
            "item_id": entry.curriculum_item_id,
            "subject_id": entry.subject_id,
            "material_fingerprint": entry.material_fingerprint,
            "stale": entry.material_fingerprint != current_fingerprint,
            "content_load": entry.content_load,
            "content_load_label": LEVELS.get(entry.content_load, "Media"),
            "conceptual_complexity": entry.conceptual_complexity,
            "conceptual_complexity_label": LEVELS.get(entry.conceptual_complexity, "Media"),
            "academic_importance": entry.academic_importance,
            "academic_importance_label": {1: "Baja", 2: "Media", 3: "Alta"}.get(entry.academic_importance, "Media"),
            "confidence": entry.confidence,
            "estimated_minutes": entry.estimated_minutes,
            "rationale": entry.rationale,
            "source_chunk_count": len(source_chunk_ids),
            "diagnostic_available": bool(safe_questions),
            "diagnostic_questions": safe_questions,
            "diagnostic_completed": entry.diagnostic_completed_at is not None,
            "diagnostic_mastery": entry.diagnostic_mastery,
            "diagnostic_scores": scores,
            "provider": entry.provider,
            "model": entry.model,
            "analysis_version": entry.analysis_version,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        },
    }


def get_topic_analysis(item_id: int, *, session_factory=SessionLocal) -> dict[str, Any]:
    item, subject = _validate_item(item_id, session_factory=session_factory)
    if item is None or subject is None:
        return {"ok": False, "error": "El Topic/Subtopic no está disponible"}
    current_fingerprint = _material_fingerprint(subject.id, session_factory=session_factory)
    with session_factory() as session:
        entry = session.scalar(select(StudyTopicAnalysis).where(
            StudyTopicAnalysis.curriculum_item_id == item_id
        ))
        if entry is None:
            return {
                "ok": True,
                "analysis": None,
                "item": {"id": item.id, "name": item.name, "type": item.item_type},
            }
        return _analysis_to_dict(entry, current_fingerprint=current_fingerprint)


def _analysis_context(item: CurriculumItem, subject: Subject, *, session_factory=SessionLocal) -> tuple[str, list[int]]:
    subtopics = _subtopic_names(item.id, session_factory=session_factory) if item.item_type == "topic" else []
    query = item.name
    if subtopics:
        query += " | " + " | ".join(subtopics[:10])
    ranked = retrieve_ranked_chunks(
        query=query,
        subject_id=subject.id,
        semantic_weight=0.72,
        ranking_context="study",
    )
    selected = select_context_chunks(
        ranked,
        minimum_score=0.12,
        maximum_sources=8,
        maximum_context_characters=9500,
        redundancy_threshold=0.88,
    )
    return build_context_text(selected), [candidate.chunk.id for candidate in selected]


def analyze_topic(
    item_id: int,
    *,
    force: bool = False,
    session_factory=SessionLocal,
    provider_factory=create_provider,
) -> dict[str, Any]:
    item, subject = _validate_item(item_id, session_factory=session_factory)
    if item is None or subject is None:
        return {"ok": False, "error": "El Topic/Subtopic no está disponible"}

    fingerprint = _material_fingerprint(subject.id, session_factory=session_factory)
    with session_factory() as session:
        cached = session.scalar(select(StudyTopicAnalysis).where(
            StudyTopicAnalysis.curriculum_item_id == item_id
        ))
        if cached is not None and cached.material_fingerprint == fingerprint and not force:
            result = _analysis_to_dict(cached, current_fingerprint=fingerprint)
            result["cache_hit"] = True
            return result

    context, source_chunk_ids = _analysis_context(item, subject, session_factory=session_factory)
    if not context.strip():
        return {
            "ok": False,
            "error": "No hay suficiente material indexado relacionado con este tema para analizarlo.",
        }

    subtopics = _subtopic_names(item.id, session_factory=session_factory) if item.item_type == "topic" else []
    system = (
        "You are analysing one university curriculum topic for study planning. "
        "Use only the supplied material. Do not infer the student's mastery. "
        "Distinguish academic importance from content difficulty: academic importance means how central the topic is "
        "inside the supplied course material, while complexity means how demanding the concepts are. "
        "A long topic is not automatically important or difficult. Return JSON only with: "
        "content_load ('low'|'medium'|'high'), conceptual_complexity ('low'|'medium'|'high'), "
        "academic_importance (1|2|3), confidence (0-100), estimated_minutes (10-90), rationale (max 3 short sentences)."
    )
    user = (
        f"Subject: {subject.name}\n"
        f"Academic language: {subject.academic_language}\n"
        f"Curriculum item: {item.name}\n"
        f"Subtopics: {', '.join(subtopics) if subtopics else 'None'}\n\n"
        "Representative material:\n"
        f"{context}"
    )
    settings = get_ai_settings()
    provider = provider_factory(settings=settings, requested_provider=None)
    generation = provider.generate(GenerationRequest(
        system_message=system,
        user_message=user,
        maximum_output_tokens=420,
    ))
    if not generation.ok:
        return {"ok": False, "error": generation.error or "UniCore no pudo completar el análisis"}

    parsed = extract_json_object(generation.text or "") or {}
    content_load = str(parsed.get("content_load") or "").strip().casefold()
    complexity = str(parsed.get("conceptual_complexity") or "").strip().casefold()
    importance = parsed.get("academic_importance")
    confidence = parsed.get("confidence")
    estimated_minutes = parsed.get("estimated_minutes")
    rationale = " ".join(str(parsed.get("rationale") or "").strip().split())
    if content_load not in LEVELS or complexity not in LEVELS or importance not in {1, 2, 3}:
        return {"ok": False, "error": "El análisis de UniCore no devolvió una estructura válida"}
    confidence_value = _clamp(float(confidence)) if isinstance(confidence, (int, float)) else None
    minutes_value = int(_clamp(float(estimated_minutes), 10, 90)) if isinstance(estimated_minutes, (int, float)) else None

    with session_factory() as session:
        entry = session.scalar(select(StudyTopicAnalysis).where(
            StudyTopicAnalysis.curriculum_item_id == item_id
        ))
        if entry is None:
            entry = StudyTopicAnalysis(
                subject_id=subject.id,
                curriculum_item_id=item.id,
                material_fingerprint=fingerprint,
            )
            session.add(entry)
        entry.subject_id = subject.id
        entry.material_fingerprint = fingerprint
        entry.content_load = content_load
        entry.conceptual_complexity = complexity
        entry.academic_importance = int(importance)
        entry.confidence = confidence_value
        entry.estimated_minutes = minutes_value
        entry.rationale = rationale or None
        entry.source_chunk_ids_json = json.dumps(source_chunk_ids)
        entry.provider = generation.provider
        entry.model = generation.model
        entry.analysis_version = ANALYSIS_VERSION
        # Si cambió el material, el diagnóstico previo ya no se considera evidencia vigente.
        if cached is not None and cached.material_fingerprint != fingerprint:
            entry.diagnostic_questions_json = None
            entry.diagnostic_answers_json = None
            entry.diagnostic_scores_json = None
            entry.diagnostic_mastery = None
            entry.diagnostic_completed_at = None
        session.commit()
        session.refresh(entry)
        result = _analysis_to_dict(entry, current_fingerprint=fingerprint)

    record_token_usage(
        usage={
            "input_tokens": generation.input_tokens,
            "output_tokens": generation.output_tokens,
            "total_tokens": generation.total_tokens,
        },
        feature="study_topic_analysis",
        subject_id=subject.id,
        provider=generation.provider,
        model=generation.model,
    )
    result["cache_hit"] = False
    return result


def _load_source_context(entry: StudyTopicAnalysis, *, session_factory=SessionLocal) -> str:
    try:
        chunk_ids = [int(value) for value in json.loads(entry.source_chunk_ids_json or "[]")]
    except (TypeError, ValueError, json.JSONDecodeError):
        chunk_ids = []
    if not chunk_ids:
        return ""
    with session_factory() as session:
        chunks = list(session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.id.in_(chunk_ids))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        ))
    return "\n\n".join(chunk.content for chunk in chunks)[:9500]


def create_diagnostic_questions(
    item_id: int,
    *,
    session_factory=SessionLocal,
    provider_factory=create_provider,
) -> dict[str, Any]:
    item, subject = _validate_item(item_id, session_factory=session_factory)
    if item is None or subject is None:
        return {"ok": False, "error": "El Topic/Subtopic no está disponible"}

    analysis_result = analyze_topic(
        item_id,
        force=False,
        session_factory=session_factory,
        provider_factory=provider_factory,
    )
    if not analysis_result.get("ok"):
        return analysis_result

    fingerprint = _material_fingerprint(subject.id, session_factory=session_factory)
    with session_factory() as session:
        entry = session.scalar(select(StudyTopicAnalysis).where(
            StudyTopicAnalysis.curriculum_item_id == item_id
        ))
        if entry is None:
            return {"ok": False, "error": "Falta el análisis inicial del tema"}
        if entry.diagnostic_questions_json and entry.material_fingerprint == fingerprint:
            result = _analysis_to_dict(entry, current_fingerprint=fingerprint)
            result["cache_hit"] = True
            return result
        context = _load_source_context(entry, session_factory=session_factory)

    if not context:
        return {"ok": False, "error": "No hay contexto suficiente para generar las preguntas"}

    system = (
        "Create exactly two short open university questions about the requested topic, using only the supplied material. "
        "Question 1 must be medium difficulty and test understanding/application. Question 2 must be hard and require "
        "comparison, reasoning or application. Avoid trivia and wording copied from the material. Return JSON only: "
        "{\"questions\":[{\"level\":\"medium\",\"question\":\"...\",\"reference_answer\":\"...\"},"
        "{\"level\":\"hard\",\"question\":\"...\",\"reference_answer\":\"...\"}]}"
    )
    user = f"Subject: {subject.name}\nTopic: {item.name}\nAcademic language: {subject.academic_language}\n\nMaterial:\n{context}"
    settings = get_ai_settings()
    provider = provider_factory(settings=settings, requested_provider=None)
    generation = provider.generate(GenerationRequest(
        system_message=system,
        user_message=user,
        maximum_output_tokens=650,
    ))
    if not generation.ok:
        return {"ok": False, "error": generation.error or "No se pudieron crear las preguntas"}
    parsed = extract_json_object(generation.text or "") or {}
    questions = parsed.get("questions")
    if not isinstance(questions, list) or len(questions) != 2:
        return {"ok": False, "error": "UniCore no devolvió exactamente dos preguntas válidas"}
    cleaned: list[dict[str, str]] = []
    expected_levels = ["medium", "hard"]
    for index, raw in enumerate(questions):
        if not isinstance(raw, dict):
            return {"ok": False, "error": "Una de las preguntas no es válida"}
        question = " ".join(str(raw.get("question") or "").strip().split())
        reference = " ".join(str(raw.get("reference_answer") or "").strip().split())
        if not question or not reference:
            return {"ok": False, "error": "Una de las preguntas quedó incompleta"}
        cleaned.append({"level": expected_levels[index], "question": question, "reference_answer": reference})

    with session_factory() as session:
        entry = session.scalar(select(StudyTopicAnalysis).where(
            StudyTopicAnalysis.curriculum_item_id == item_id
        ))
        if entry is None:
            return {"ok": False, "error": "Falta el análisis inicial del tema"}
        entry.diagnostic_questions_json = json.dumps(cleaned, ensure_ascii=False)
        entry.diagnostic_answers_json = None
        entry.diagnostic_scores_json = None
        entry.diagnostic_mastery = None
        entry.diagnostic_completed_at = None
        session.commit()
        session.refresh(entry)
        result = _analysis_to_dict(entry, current_fingerprint=fingerprint)

    record_token_usage(
        usage={
            "input_tokens": generation.input_tokens,
            "output_tokens": generation.output_tokens,
            "total_tokens": generation.total_tokens,
        },
        feature="study_topic_diagnostic_questions",
        subject_id=subject.id,
        provider=generation.provider,
        model=generation.model,
    )
    result["cache_hit"] = False
    return result


def grade_diagnostic_answers(
    item_id: int,
    answers: list[str],
    *,
    session_factory=SessionLocal,
    provider_factory=create_provider,
) -> dict[str, Any]:
    item, subject = _validate_item(item_id, session_factory=session_factory)
    if item is None or subject is None:
        return {"ok": False, "error": "El Topic/Subtopic no está disponible"}
    if len(answers) != 2 or any(len(str(answer).strip()) < 3 for answer in answers):
        return {"ok": False, "error": "Responde las dos preguntas antes de continuar"}

    fingerprint = _material_fingerprint(subject.id, session_factory=session_factory)
    with session_factory() as session:
        entry = session.scalar(select(StudyTopicAnalysis).where(
            StudyTopicAnalysis.curriculum_item_id == item_id
        ))
        if entry is None or not entry.diagnostic_questions_json:
            return {"ok": False, "error": "Primero genera las dos preguntas"}
        if entry.material_fingerprint != fingerprint:
            return {"ok": False, "error": "El material cambió. Repite el análisis antes del diagnóstico"}
        try:
            questions = json.loads(entry.diagnostic_questions_json)
        except json.JSONDecodeError:
            return {"ok": False, "error": "Las preguntas guardadas no son válidas"}

    evaluation_rows = []
    for question, answer in zip(questions, answers):
        evaluation_rows.append({
            "level": question.get("level"),
            "question": question.get("question"),
            "reference_answer": question.get("reference_answer"),
            "student_answer": str(answer).strip(),
        })

    system = (
        "Act as a strict but fair university grader. Grade each answer only against the supplied reference and question. "
        "Partial knowledge must receive partial credit. Return JSON only: "
        "{\"scores\":[{\"level\":\"medium\",\"score\":0-100,\"feedback\":\"short\"},"
        "{\"level\":\"hard\",\"score\":0-100,\"feedback\":\"short\"}]}"
    )
    user = json.dumps(evaluation_rows, ensure_ascii=False)
    settings = get_ai_settings()
    provider = provider_factory(settings=settings, requested_provider=None)
    generation = provider.generate(GenerationRequest(
        system_message=system,
        user_message=user,
        maximum_output_tokens=520,
    ))
    if not generation.ok:
        return {"ok": False, "error": generation.error or "No se pudieron evaluar las respuestas"}
    parsed = extract_json_object(generation.text or "") or {}
    scores = parsed.get("scores")
    if not isinstance(scores, list) or len(scores) != 2:
        return {"ok": False, "error": "La evaluación no devolvió dos resultados válidos"}

    cleaned_scores: list[dict[str, Any]] = []
    numeric_scores: list[float] = []
    for index, raw in enumerate(scores):
        if not isinstance(raw, dict) or not isinstance(raw.get("score"), (int, float)):
            return {"ok": False, "error": "La evaluación devolvió una puntuación inválida"}
        score = round(_clamp(float(raw["score"])), 1)
        numeric_scores.append(score)
        cleaned_scores.append({
            "level": "medium" if index == 0 else "hard",
            "score": score,
            "feedback": " ".join(str(raw.get("feedback") or "").strip().split()),
        })

    # La pregunta difícil pesa algo más porque ofrece evidencia más fuerte de dominio.
    mastery = round(numeric_scores[0] * 0.4 + numeric_scores[1] * 0.6, 1)
    with session_factory() as session:
        entry = session.scalar(select(StudyTopicAnalysis).where(
            StudyTopicAnalysis.curriculum_item_id == item_id
        ))
        if entry is None:
            return {"ok": False, "error": "Falta el análisis inicial del tema"}
        entry.diagnostic_answers_json = json.dumps([str(answer).strip() for answer in answers], ensure_ascii=False)
        entry.diagnostic_scores_json = json.dumps(cleaned_scores, ensure_ascii=False)
        entry.diagnostic_mastery = mastery
        entry.diagnostic_completed_at = datetime.utcnow()
        session.commit()
        session.refresh(entry)
        result = _analysis_to_dict(entry, current_fingerprint=fingerprint)

    record_token_usage(
        usage={
            "input_tokens": generation.input_tokens,
            "output_tokens": generation.output_tokens,
            "total_tokens": generation.total_tokens,
        },
        feature="study_topic_diagnostic_grade",
        subject_id=subject.id,
        provider=generation.provider,
        model=generation.model,
    )
    result["mastery"] = mastery
    return result