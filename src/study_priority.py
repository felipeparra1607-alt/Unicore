from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from src.curriculum_engine import normalize_curriculum_name
from src.database.connection import SessionLocal
from src.database.models import (
    CurriculumChunkReference,
    CurriculumItem,
    Document,
    DocumentChunk,
    ReviewItem,
    StudyAttempt,
    StudySession,
    StudyTopicAnalysis,
    Subject,
)

IMPORTANCE_LABELS = {1: "Baja", 2: "Media", 3: "Alta"}
COMPLEXITY_SCORES = {"low": 25.0, "medium": 55.0, "high": 85.0}
LOAD_SCORES = {"low": 25.0, "medium": 55.0, "high": 85.0}
LOAD_MINUTES = {"low": 15, "medium": 30, "high": 50}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _days_since(value: datetime | None) -> int | None:
    if value is None:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return max(0, (now - value).days)


def _descendant_ids(items: list[CurriculumItem], item_id: int) -> set[int]:
    children: dict[int, list[int]] = {}
    for item in items:
        if item.parent_id is not None:
            children.setdefault(item.parent_id, []).append(item.id)
    result = {item_id}
    queue = [item_id]
    while queue:
        current = queue.pop()
        for child_id in children.get(current, []):
            if child_id not in result:
                result.add(child_id)
                queue.append(child_id)
    return result


def _automatic_importance(
    *,
    content_characters: int,
    chunk_count: int,
    subtopic_count: int,
) -> tuple[int, float]:
    """Fallback determinista mientras el usuario no elija manual o UniCore."""

    content_points = min(48.0, content_characters / 650.0)
    chunk_points = min(22.0, chunk_count * 2.2)
    structure_points = min(20.0, subtopic_count * 4.0)
    score = _clamp(20.0 + content_points + chunk_points + structure_points)
    level = 3 if score >= 70 else 2 if score >= 42 else 1
    return level, round(score, 1)


def _subject_material_fingerprint(subject_id: int, session) -> str:
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


def set_curriculum_importance(
    item_id: int,
    *,
    mode: str,
    level: int | None = None,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    clean_mode = mode.casefold().strip()
    if clean_mode == "auto":
        # Compatibilidad con versiones anteriores de la interfaz.
        clean_mode = "unicore"
    if clean_mode not in {"unicore", "manual"}:
        return {"ok": False, "error": "mode debe ser unicore o manual"}
    if clean_mode == "manual" and level not in {1, 2, 3}:
        return {"ok": False, "error": "La importancia manual debe ser 1, 2 o 3"}

    with session_factory() as session:
        item = session.get(CurriculumItem, item_id)
        if item is None or item.item_type not in {"topic", "subtopic"}:
            return {"ok": False, "error": "El Topic/Subtopic no existe"}
        if clean_mode == "unicore":
            analysis = session.scalar(select(StudyTopicAnalysis).where(
                StudyTopicAnalysis.curriculum_item_id == item_id
            ))
            if analysis is None:
                return {"ok": False, "error": "Primero completa el análisis de UniCore"}
            current_fingerprint = _subject_material_fingerprint(item.subject_id, session)
            if analysis.material_fingerprint != current_fingerprint:
                return {"ok": False, "error": "El material cambió. Repite el análisis de UniCore"}
        item.importance_mode = clean_mode
        item.manual_importance = level if clean_mode == "manual" else None
        session.commit()
        return {
            "ok": True,
            "item_id": item.id,
            "importance_mode": item.importance_mode,
            "manual_importance": item.manual_importance,
        }


def study_priority_for_subject(
    subject_id: int,
    *,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    with session_factory() as session:
        subject = session.get(Subject, subject_id)
        if subject is None:
            return {"ok": False, "error": "La asignatura no existe"}

        items = list(session.scalars(
            select(CurriculumItem)
            .where(
                CurriculumItem.subject_id == subject_id,
                CurriculumItem.item_type.in_(["topic", "subtopic"]),
                CurriculumItem.source != "rejected",
                CurriculumItem.manually_locked.is_(True),
            )
            .order_by(CurriculumItem.position, CurriculumItem.id)
        ))
        all_subject_items = list(session.scalars(
            select(CurriculumItem).where(CurriculumItem.subject_id == subject_id)
        ))

        review_items = list(session.scalars(
            select(ReviewItem).where(
                ReviewItem.subject_id == subject_id,
                ReviewItem.status != "rejected",
            )
        ))
        quiz_attempts = list(session.scalars(
            select(StudyAttempt).where(
                StudyAttempt.subject_id == subject_id,
                StudyAttempt.status == "completed",
            )
        ))
        study_sessions = list(session.scalars(
            select(StudySession).where(StudySession.subject_id == subject_id)
        ))
        analyses = list(session.scalars(
            select(StudyTopicAnalysis).where(StudyTopicAnalysis.subject_id == subject_id)
        ))
        analysis_by_item = {entry.curriculum_item_id: entry for entry in analyses}
        current_fingerprint = _subject_material_fingerprint(subject_id, session)

        chunk_rows = list(session.execute(
            select(
                CurriculumChunkReference.curriculum_item_id,
                DocumentChunk.id,
                DocumentChunk.char_start,
                DocumentChunk.char_end,
            )
            .join(DocumentChunk, DocumentChunk.id == CurriculumChunkReference.chunk_id)
            .where(CurriculumChunkReference.curriculum_item_id.in_([i.id for i in all_subject_items]))
        )) if all_subject_items else []

        chunk_by_item: dict[int, dict[int, int]] = {}
        for curriculum_item_id, chunk_id, char_start, char_end in chunk_rows:
            chunk_by_item.setdefault(curriculum_item_id, {})[chunk_id] = max(
                0, int(char_end or 0) - int(char_start or 0)
            )

        normalized_names = {item.id: normalize_curriculum_name(item.name) for item in all_subject_items}
        metrics: list[dict[str, Any]] = []

        for item in items:
            scope_ids = _descendant_ids(all_subject_items, item.id) if item.item_type == "topic" else {item.id}
            scope_names = {normalized_names[cid] for cid in scope_ids if cid in normalized_names}

            unique_chunks: dict[int, int] = {}
            for scope_id in scope_ids:
                unique_chunks.update(chunk_by_item.get(scope_id, {}))
            content_characters = sum(unique_chunks.values())
            chunk_count = len(unique_chunks)
            subtopic_count = sum(
                1 for candidate in all_subject_items
                if candidate.parent_id == item.id
                and candidate.item_type == "subtopic"
                and candidate.source != "rejected"
            )

            scoped_cards = []
            for card in review_items:
                if card.curriculum_item_id in scope_ids:
                    scoped_cards.append(card)
                    continue
                if card.curriculum_item_id is None and normalize_curriculum_name(card.topic) in scope_names:
                    scoped_cards.append(card)

            flashcard_reviews = sum(max(0, card.repetition_count or 0) for card in scoped_cards)
            flashcard_errors = sum(max(0, card.incorrect_count or 0) for card in scoped_cards)
            flashcard_accuracy = None
            if flashcard_reviews > 0:
                flashcard_accuracy = _clamp(
                    100.0 * max(0, flashcard_reviews - flashcard_errors) / flashcard_reviews
                )

            scoped_quizzes = [
                attempt for attempt in quiz_attempts
                if normalize_curriculum_name(attempt.topic) in scope_names
                and attempt.score_percentage is not None
            ]
            quiz_average = (
                sum(float(attempt.score_percentage) for attempt in scoped_quizzes) / len(scoped_quizzes)
                if scoped_quizzes else None
            )

            analysis = analysis_by_item.get(item.id)
            analysis_current = bool(analysis and analysis.material_fingerprint == current_fingerprint)
            diagnostic_mastery = (
                float(analysis.diagnostic_mastery)
                if analysis_current and analysis and analysis.diagnostic_mastery is not None
                else None
            )

            evidence_scores: list[tuple[float, float]] = []
            if flashcard_accuracy is not None:
                evidence_scores.append((flashcard_accuracy, 0.55))
            if quiz_average is not None:
                evidence_scores.append((float(quiz_average), 0.45 if flashcard_accuracy is not None else 1.0))
            if diagnostic_mastery is not None:
                # El diagnóstico es evidencia inicial; cuando hay historial real pesa menos.
                evidence_scores.append((diagnostic_mastery, 0.30 if evidence_scores else 1.0))
            if evidence_scores:
                mastery = sum(score * weight for score, weight in evidence_scores) / sum(weight for _, weight in evidence_scores)
                mastery = round(_clamp(mastery), 1)
            else:
                mastery = None

            last_reviewed = max(
                (card.last_reviewed_at for card in scoped_cards if card.last_reviewed_at is not None),
                default=None,
            )
            last_study = max(
                (
                    session_row.completed_at or session_row.started_at
                    for session_row in study_sessions
                    if session_row.topic and normalize_curriculum_name(session_row.topic) in scope_names
                    and (session_row.completed_at or session_row.started_at)
                ),
                default=None,
            )
            last_activity = max([value for value in [last_reviewed, last_study] if value is not None], default=None)
            days_since_activity = _days_since(last_activity)

            fallback_level, fallback_score = _automatic_importance(
                content_characters=content_characters,
                chunk_count=chunk_count,
                subtopic_count=subtopic_count,
            )
            if item.importance_mode == "manual" and item.manual_importance in {1, 2, 3}:
                importance_level = int(item.manual_importance)
                importance_source = "manual"
            elif item.importance_mode == "unicore" and analysis_current and analysis is not None:
                importance_level = int(analysis.academic_importance)
                importance_source = "unicore"
            else:
                importance_level = fallback_level
                importance_source = "fallback"
            importance_score = {1: 35.0, 2: 65.0, 3: 90.0}[importance_level]

            if mastery is None:
                personal_difficulty = None
                lack_of_mastery = 55.0
            else:
                personal_difficulty = round(_clamp(100.0 - mastery), 1)
                lack_of_mastery = 100.0 - mastery

            complexity = analysis.conceptual_complexity if analysis_current and analysis is not None else None
            content_load = analysis.content_load if analysis_current and analysis is not None else None
            complexity_score = COMPLEXITY_SCORES.get(complexity or "", 50.0)
            load_score = LOAD_SCORES.get(content_load or "", 50.0)
            recency_score = 25.0 if days_since_activity is None else _clamp(days_since_activity * 6.0)
            priority_score = _clamp(
                importance_score * 0.30
                + lack_of_mastery * 0.40
                + recency_score * 0.10
                + complexity_score * 0.10
                + load_score * 0.10
            )

            if analysis_current and analysis is not None:
                base_minutes = int(analysis.estimated_minutes or LOAD_MINUTES.get(analysis.content_load, 30))
            else:
                base_minutes = int(_clamp(18 + content_characters / 850 + subtopic_count * 5, 15, 75))
            difficulty_factor = 1.0 if personal_difficulty is None else 0.75 + personal_difficulty / 140.0
            mastery_factor = 1.0 if mastery is None else 0.55 + (100.0 - mastery) / 135.0
            estimated_minutes = int(round(_clamp(base_minutes * difficulty_factor * mastery_factor, 10, 90) / 5.0) * 5)

            if priority_score >= 75:
                priority_label = "Muy alta"
            elif priority_score >= 60:
                priority_label = "Alta"
            elif priority_score >= 42:
                priority_label = "Media"
            else:
                priority_label = "Baja"

            metrics.append({
                "item_id": item.id,
                "item_type": item.item_type,
                "name": item.name,
                "parent_id": item.parent_id,
                "importance_mode": item.importance_mode or "auto",
                "manual_importance": item.manual_importance,
                "importance_source": importance_source,
                "importance_level": importance_level,
                "importance_label": IMPORTANCE_LABELS[importance_level],
                "automatic_importance_score": fallback_score,
                "content_characters": content_characters,
                "chunk_count": chunk_count,
                "subtopic_count": subtopic_count,
                "flashcard_count": len(scoped_cards),
                "flashcard_reviews": flashcard_reviews,
                "flashcard_errors": flashcard_errors,
                "flashcard_accuracy": round(flashcard_accuracy, 1) if flashcard_accuracy is not None else None,
                "quiz_count": len(scoped_quizzes),
                "quiz_average": round(float(quiz_average), 1) if quiz_average is not None else None,
                "diagnostic_mastery": round(diagnostic_mastery, 1) if diagnostic_mastery is not None else None,
                "mastery": mastery,
                "personal_difficulty": personal_difficulty,
                "content_complexity": complexity,
                "content_load": content_load,
                "analysis_available": analysis_current,
                "analysis_stale": bool(analysis and not analysis_current),
                "days_since_activity": days_since_activity,
                "priority_score": round(priority_score, 1),
                "priority_label": priority_label,
                "estimated_minutes": estimated_minutes,
                "needs_diagnostic": mastery is None,
            })

        recommendations = sorted(
            [item for item in metrics if item["item_type"] == "topic"],
            key=lambda value: (-float(value["priority_score"]), value["item_id"]),
        )

        return {
            "ok": True,
            "subject": {"id": subject.id, "name": subject.name},
            "items": metrics,
            "recommendations": recommendations[:5],
            "method": {
                "importance": "manual_or_unicore_analysis_with_deterministic_fallback",
                "mastery": "flashcards_quizzes_and_optional_diagnostic",
                "difficulty": "unicore_content_complexity_then_personal_performance",
                "note": "El análisis de UniCore se guarda y solo se invalida cuando cambian los materiales de la asignatura.",
            },
        }