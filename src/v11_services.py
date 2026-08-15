from __future__ import annotations

import json
import re
import hashlib
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from difflib import SequenceMatcher
from typing import Any, Callable

from sqlalchemy import func, or_, select

from src.ai_config import get_ai_settings
from src.database.connection import SessionLocal
from src.database.models import (
    Document,
    ExplanationCache,
    FlashcardDraft,
    KnowledgeConcept,
    KnowledgeConnection,
    Professor,
    ProfessorAssignment,
    ProfessorPreference,
    ReviewItem,
    RubricCriterion,
    StudentModelEvidence,
    Subject,
    TokenUsage,
    WrittenEvaluation,
)
from src.providers import create_provider
from src.providers.base import GenerationRequest
from src.rag_tools import retrieve_ranked_chunks, select_context_chunks
from src.review_tools import review_item_to_dict
from src.study_tools import extract_json_object


LEITNER_INTERVALS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
LEITNER_NAMES = {
    1: "Aprendiendo",
    2: "Familiar",
    3: "Consolidando",
    4: "Dominado",
    5: "Largo plazo",
}
COGNITIVE_LEVELS = {"recall", "understanding", "application", "analysis", "mixed"}
ANSWER_MODES = {"mental", "written", "mixed"}


def _explanation_key(topic: str) -> str:
    return " ".join(re.findall(r"[\wáéíóúüñ]+", topic.casefold(), flags=re.UNICODE))


def _explanation_fingerprint(*, subject_id: int, document_id: int | None, allowed_document_ids: list[int] | None, session) -> str:
    statement = select(Document.id, Document.content_hash, Document.curriculum_processed_at).where(Document.subject_id == subject_id)
    if document_id is not None:
        statement = statement.where(Document.id == document_id)
    elif allowed_document_ids is not None:
        # Una selección vacía significa que el tema todavía no tiene fuentes;
        # no debe ampliar silenciosamente el fingerprint a toda la asignatura.
        statement = statement.where(Document.id.in_(allowed_document_ids or [-1]))
    rows = session.execute(statement.order_by(Document.id)).all()
    stable = "|".join(f"{row.id}:{row.content_hash or ''}:{row.curriculum_processed_at or ''}" for row in rows)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def cached_explanation(*, subject_id: int, document_id: int | None, curriculum_item_id: int | None, topic: str, difficulty: str, allowed_document_ids: list[int] | None = None, session_factory=SessionLocal) -> dict[str, Any] | None:
    with session_factory() as session:
        fingerprint = _explanation_fingerprint(subject_id=subject_id, document_id=document_id, allowed_document_ids=allowed_document_ids, session=session)
        statement = select(ExplanationCache).where(
            ExplanationCache.subject_id == subject_id,
            ExplanationCache.document_id == document_id,
            ExplanationCache.curriculum_item_id == curriculum_item_id,
            ExplanationCache.topic_key == _explanation_key(topic),
            ExplanationCache.difficulty == difficulty,
            ExplanationCache.material_fingerprint == fingerprint,
        ).order_by(ExplanationCache.updated_at.desc())
        entry = session.scalar(statement)
        if entry is None:
            return None
        return {"content": entry.content, "sources": json.loads(entry.sources_json or "[]"), "fingerprint": fingerprint, "updated_at": entry.updated_at.isoformat()}


def store_explanation_cache(*, subject_id: int, document_id: int | None, curriculum_item_id: int | None, topic: str, difficulty: str, content: str, sources: list[dict], allowed_document_ids: list[int] | None = None, session_factory=SessionLocal) -> None:
    with session_factory() as session:
        fingerprint = _explanation_fingerprint(subject_id=subject_id, document_id=document_id, allowed_document_ids=allowed_document_ids, session=session)
        entry = ExplanationCache(subject_id=subject_id, document_id=document_id, curriculum_item_id=curriculum_item_id, topic_key=_explanation_key(topic), difficulty=difficulty, material_fingerprint=fingerprint, content=content, sources_json=json.dumps(sources, ensure_ascii=False))
        session.add(entry)
        session.commit()


def record_token_usage(
    *,
    usage: dict[str, Any] | None,
    feature: str,
    subject_id: int | None = None,
    conversation_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    usage = usage or {}
    values = {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
    missing_provider_usage = (
        int(usage.get("model_calls") or 0) > 0
        and all(value in {None, 0} for value in values.values())
    )
    if all(value is None for value in values.values()) or missing_provider_usage:
        return {"available": False, **values}
    if values["total_tokens"] is None and values["input_tokens"] is not None and values["output_tokens"] is not None:
        values["total_tokens"] = values["input_tokens"] + values["output_tokens"]
    with session_factory() as session:
        entry = TokenUsage(
            feature=feature,
            subject_id=subject_id,
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            **values,
        )
        session.add(entry)
        session.commit()
    return {"available": True, **values}


def token_analytics(*, days: int = 14, session_factory=SessionLocal) -> dict[str, Any]:
    days = max(7, min(days, 90))
    today = date.today()
    start = today - timedelta(days=days - 1)
    with session_factory() as session:
        records = list(session.scalars(
            select(TokenUsage).where(TokenUsage.created_at >= datetime.combine(start, time.min))
        ))
        subjects = {item.id: item.name for item in session.scalars(select(Subject))}
    daily = {
        start + timedelta(days=offset): {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "request_count": 0}
        for offset in range(days)
    }
    subject_totals: dict[int | None, dict[str, Any]] = defaultdict(
        lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "request_count": 0}
    )
    for item in records:
        bucket = daily[item.created_at.date()]
        subject_bucket = subject_totals[item.subject_id]
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(item, key) or 0
            bucket[key] += value
            subject_bucket[key] += value
        bucket["request_count"] += 1
        subject_bucket["request_count"] += 1
    week_start = today - timedelta(days=6)
    return {
        "ok": True,
        "today": daily[today]["total_tokens"],
        "this_week": sum(value["total_tokens"] for day_value, value in daily.items() if day_value >= week_start),
        "daily": [{"date": key.isoformat(), **value} for key, value in sorted(daily.items())],
        "by_subject": [
            {"subject_id": key, "subject_name": subjects.get(key, "Sin asignatura"), **value}
            for key, value in sorted(subject_totals.items(), key=lambda item: item[1]["total_tokens"], reverse=True)
        ],
    }


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[\wáéíóúüñ]+", value.casefold(), flags=re.UNICODE))


def lexical_similarity(first: str, second: str) -> float:
    clean_first = _normalized_text(first)
    clean_second = _normalized_text(second)
    if not clean_first or not clean_second:
        return 0.0
    first_words = set(clean_first.split())
    second_words = set(clean_second.split())
    union = first_words | second_words
    jaccard = len(first_words & second_words) / len(union) if union else 0.0
    return max(jaccard, SequenceMatcher(None, clean_first, clean_second).ratio())


def create_flashcard_drafts(
    *,
    subject_id: int,
    topic: str,
    cards: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    cognitive_level: str,
    answer_mode: str,
    document_id: int | None = None,
    session_factory=SessionLocal,
) -> list[dict[str, Any]]:
    level = cognitive_level.casefold()
    mode = answer_mode.casefold()
    if level not in COGNITIVE_LEVELS or mode not in ANSWER_MODES:
        raise ValueError("Nivel cognitivo o modo de respuesta no válido")
    with session_factory() as session:
        existing = list(session.scalars(select(ReviewItem).where(ReviewItem.subject_id == subject_id)))
        drafts = []
        for card in cards:
            question = " ".join(str(card.get("front", "")).split())
            answer = " ".join(str(card.get("back", "")).split())
            if not question or not answer:
                continue
            card_level = str(card.get("cognitive_level") or level).casefold()
            if card_level not in COGNITIVE_LEVELS:
                card_level = level
            closest = max(existing, key=lambda item: lexical_similarity(question, item.question), default=None)
            similarity = lexical_similarity(question, closest.question) if closest else 0.0
            draft = FlashcardDraft(
                subject_id=subject_id,
                document_id=document_id,
                topic=topic,
                question=question,
                correct_answer=answer,
                sources_json=json.dumps(sources, ensure_ascii=False),
                cognitive_level=card_level,
                answer_mode=mode,
                probable_duplicate=similarity >= 0.82,
                duplicate_review_item_id=closest.id if closest and similarity >= 0.82 else None,
            )
            session.add(draft)
            session.flush()
            drafts.append(flashcard_draft_to_dict(draft))
        session.commit()
        return drafts


def flashcard_draft_to_dict(item: FlashcardDraft) -> dict[str, Any]:
    return {
        "id": item.id,
        "subject_id": item.subject_id,
        "document_id": item.document_id,
        "topic": item.topic,
        "question": item.question,
        "correct_answer": item.correct_answer,
        "sources": json.loads(item.sources_json or "[]"),
        "cognitive_level": item.cognitive_level,
        "answer_mode": item.answer_mode,
        "probable_duplicate": item.probable_duplicate,
        "status": item.status,
        "rejection_reason": item.rejection_reason,
    }


def decide_flashcard_draft(
    draft_id: int,
    *,
    accept: bool,
    rejection_reason: str | None = None,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    now = datetime.utcnow()
    with session_factory() as session:
        draft = session.get(FlashcardDraft, draft_id)
        if draft is None:
            return {"ok": False, "error": "La propuesta de flashcard no existe"}
        if draft.status != "pending":
            return {"ok": False, "error": "Esta propuesta ya fue procesada"}
        draft.status = "accepted" if accept else "rejected"
        draft.decided_at = now
        if not accept:
            draft.rejection_reason = " ".join((rejection_reason or "").split()) or None
            session.commit()
            return {"ok": True, "accepted": False, "draft": flashcard_draft_to_dict(draft)}
        item = ReviewItem(
            subject_id=draft.subject_id,
            topic=draft.topic,
            question=draft.question,
            correct_answer=draft.correct_answer,
            sources_json=draft.sources_json,
            status="learning",
            priority=3,
            repetition_count=0,
            correct_streak=0,
            incorrect_count=0,
            interval_days=LEITNER_INTERVALS[1],
            ease_factor=2.5,
            leitner_box=1,
            cognitive_level=draft.cognitive_level,
            next_review_at=now,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return {"ok": True, "accepted": True, "card": review_item_to_dict(item)}


def _apply_box(item: ReviewItem, box: int, *, now: datetime) -> None:
    item.leitner_box = max(1, min(5, box))
    item.interval_days = LEITNER_INTERVALS[item.leitner_box]
    item.next_review_at = now + timedelta(days=item.interval_days)
    item.status = "mastered" if item.leitner_box >= 4 else ("reviewing" if item.leitner_box >= 2 else "learning")
    item.updated_at = now


def move_flashcard(
    review_item_id: int,
    *,
    target_box: int | None = None,
    review_earlier: bool = False,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    if target_box is not None and target_box not in LEITNER_INTERVALS:
        return {"ok": False, "error": "La box debe estar entre 1 y 5"}
    now = datetime.utcnow()
    with session_factory() as session:
        item = session.get(ReviewItem, review_item_id)
        if item is None:
            return {"ok": False, "error": "La flashcard no existe"}
        if target_box is not None:
            _apply_box(item, target_box, now=now)
        if review_earlier:
            item.next_review_at = now
            item.priority = 5
        session.commit()
        session.refresh(item)
        return {"ok": True, "card": review_item_to_dict(item)}


def rate_leitner_card(
    review_item_id: int,
    *,
    rating: str,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    clean = rating.casefold()
    if clean not in {"difficult", "good", "easy"}:
        return {"ok": False, "error": "Valoración no válida"}
    now = datetime.utcnow()
    with session_factory() as session:
        item = session.get(ReviewItem, review_item_id)
        if item is None:
            return {"ok": False, "error": "La flashcard no existe"}
        previous_box = item.leitner_box or 1
        next_box = max(1, previous_box - 1) if clean == "difficult" else min(5, previous_box + (2 if clean == "easy" else 1))
        item.repetition_count += 1
        item.last_reviewed_at = now
        item.last_rating = clean
        if clean == "difficult":
            item.correct_streak = 0
            item.incorrect_count += 1
        else:
            item.correct_streak += 1
        _apply_box(item, next_box, now=now)
        session.commit()
        session.refresh(item)
        return {"ok": True, "previous_box": previous_box, "card": review_item_to_dict(item)}


def reject_flashcard(review_item_id: int, *, session_factory=SessionLocal) -> dict[str, Any]:
    with session_factory() as session:
        item = session.get(ReviewItem, review_item_id)
        if item is None:
            return {"ok": False, "error": "La flashcard no existe"}
        item.status = "rejected"
        item.last_rating = "rejected"
        item.next_review_at = datetime.max
        session.commit()
        return {"ok": True, "rejected": True}


def leitner_overview(*, subject_id: int | None = None, session_factory=SessionLocal) -> dict[str, Any]:
    now = datetime.utcnow()
    with session_factory() as session:
        statement = select(ReviewItem).where(ReviewItem.status != "rejected")
        if subject_id is not None:
            statement = statement.where(ReviewItem.subject_id == subject_id)
        items = list(session.scalars(statement.order_by(ReviewItem.next_review_at, ReviewItem.id)))
        subjects = {item.id: item.name for item in session.scalars(select(Subject))}
    boxes = []
    for box in range(1, 6):
        box_items = [item for item in items if (item.leitner_box or 1) == box]
        boxes.append({
            "box": box,
            "name": LEITNER_NAMES[box],
            "interval_days": LEITNER_INTERVALS[box],
            "count": len(box_items),
            "due_count": sum(item.next_review_at <= now for item in box_items),
        })
    cards = []
    for item in items:
        payload = review_item_to_dict(item)
        payload["subject_name"] = subjects.get(item.subject_id)
        cards.append(payload)
    return {"ok": True, "boxes": boxes, "cards": cards}


def student_model(*, subject_id: int | None = None, session_factory=SessionLocal) -> dict[str, Any]:
    with session_factory() as session:
        statement = select(StudentModelEvidence)
        if subject_id is not None:
            statement = statement.where(StudentModelEvidence.subject_id == subject_id)
        rows = list(session.scalars(statement.order_by(StudentModelEvidence.observed_at.desc(), StudentModelEvidence.id.desc())))
    grouped: dict[str, list[StudentModelEvidence]] = defaultdict(list)
    for row in rows:
        if len(grouped[row.dimension]) < 20:
            grouped[row.dimension].append(row)
    dimensions = []
    for dimension, evidence in grouped.items():
        chronological = list(reversed(evidence))
        weights = [0.5 + (index / max(1, len(chronological) - 1)) * 0.5 for index in range(len(chronological))]
        score = sum(item.score * weight for item, weight in zip(chronological, weights)) / sum(weights)
        recent = sum(item.score for item in evidence[: min(3, len(evidence))]) / min(3, len(evidence))
        older = sum(item.score for item in evidence[3:]) / len(evidence[3:]) if len(evidence) > 3 else recent
        if score >= 75:
            status = "strength"
        elif score < 50 and recent > older + 5:
            status = "improving"
        elif score < 50:
            status = "weakness"
        else:
            status = "stable"
        dimensions.append({
            "dimension": dimension,
            "score": round(score, 1),
            "trend": round(recent - older, 1),
            "status": status,
            "evidence_count": len(evidence),
            "last_observed_at": evidence[0].observed_at.isoformat(),
        })
    dimensions.sort(key=lambda item: (item["status"] != "weakness", item["score"]))
    return {
        "ok": True,
        "dimensions": dimensions,
        "strengths": [item for item in dimensions if item["status"] == "strength"],
        "areas_for_improvement": [item for item in dimensions if item["status"] in {"weakness", "improving"}],
    }


def _professor_context(session, subject_id: int) -> str:
    preferences = list(session.scalars(
        select(ProfessorPreference).where(ProfessorPreference.subject_id == subject_id)
        .order_by(ProfessorPreference.importance.desc()).limit(6)
    ))
    rubric = list(session.scalars(
        select(RubricCriterion).where(RubricCriterion.subject_id == subject_id)
        .order_by(RubricCriterion.weight_percentage.desc().nullslast(), RubricCriterion.id).limit(6)
    ))
    lines = [f"- {item.preference}" for item in preferences]
    lines.extend(f"- {item.title}: {item.description or item.notes or ''}" for item in rubric)
    return "\n".join(lines)


def study_generation_context(*, subject_id: int, session_factory=SessionLocal) -> dict[str, str]:
    with session_factory() as session:
        subject = session.get(Subject, subject_id)
        if subject is None:
            raise ValueError("La asignatura no existe")
        professor_context = _professor_context(session, subject_id)
    model = student_model(subject_id=subject_id, session_factory=session_factory)
    relevant = [
        f"{item['dimension']}: {item['status']} ({item['score']}/100)"
        for item in (model["areas_for_improvement"][:3] + model["strengths"][:2])
    ]
    return {
        "academic_language": subject.academic_language,
        "professor_context": professor_context,
        "student_context": "\n".join(relevant),
    }


def evaluate_written_answer(
    *,
    review_item_id: int,
    answer_text: str,
    session_factory=SessionLocal,
    provider_factory=create_provider,
) -> dict[str, Any]:
    answer = answer_text.strip()
    if len(answer) < 20:
        return {"ok": False, "error": "La respuesta es demasiado breve para evaluarla con rigor"}
    with session_factory() as session:
        item = session.get(ReviewItem, review_item_id)
        if item is None:
            return {"ok": False, "error": "La flashcard no existe"}
        subject = session.get(Subject, item.subject_id)
        professor_context = _professor_context(session, item.subject_id)
        language = subject.academic_language if subject else "Spanish"
        question = item.question
        expected = item.correct_answer or ""
        subject_id = item.subject_id
    dimensions = ["content_accuracy", "depth_of_analysis", "application", "argument_quality", "relevance", "evidence_use", "professor_alignment"]
    if language.casefold() == "english":
        dimensions.append("academic_english")
    system = (
        "Act as a strict university examiner. Do not inflate scores and do not use praise to avoid criticism. "
        "Evaluate only relevant dimensions. Return JSON only with overall_score (0-100), dimensions "
        "[{name,score,feedback}], errors [string], improvements [string], example_improvement (a short targeted example). "
        "Do not rewrite the full perfect answer."
    )
    user = (
        f"Academic language: {language}\nQuestion: {question}\nReference answer: {expected}\n"
        f"Professor criteria (use only if present):\n{professor_context or 'None registered'}\n"
        f"Relevant dimensions: {', '.join(dimensions)}\nStudent answer:\n{answer}"
    )
    settings = get_ai_settings()
    provider = provider_factory(settings=settings, requested_provider=None)
    generation = provider.generate(GenerationRequest(system_message=system, user_message=user, maximum_output_tokens=850))
    if not generation.ok:
        return {"ok": False, "error": generation.error or "No se pudo evaluar la respuesta"}
    parsed = extract_json_object(generation.text or "") or {}
    parsed_dimensions = parsed.get("dimensions") if isinstance(parsed.get("dimensions"), list) else []
    overall = parsed.get("overall_score")
    if not isinstance(overall, (int, float)) or not parsed_dimensions:
        return {"ok": False, "error": "La evaluación no devolvió una estructura válida"}
    overall = max(0.0, min(100.0, float(overall)))
    with session_factory() as session:
        evaluation = WrittenEvaluation(
            review_item_id=review_item_id,
            subject_id=subject_id,
            answer_text=answer,
            overall_score=overall,
            dimensions_json=json.dumps(parsed_dimensions, ensure_ascii=False),
            errors_json=json.dumps(parsed.get("errors") or [], ensure_ascii=False),
            improvements_json=json.dumps(parsed.get("improvements") or [], ensure_ascii=False),
            example_improvement=str(parsed.get("example_improvement") or "") or None,
            provider=generation.provider,
            model=generation.model,
        )
        session.add(evaluation)
        session.flush()
        for dimension in parsed_dimensions:
            name = str(dimension.get("name") or "").strip()
            score = dimension.get("score")
            if name and isinstance(score, (int, float)):
                session.add(StudentModelEvidence(
                    subject_id=subject_id,
                    dimension=name,
                    score=max(0.0, min(100.0, float(score))),
                    source_type="written_evaluation",
                    source_id=evaluation.id,
                ))
        item = session.get(ReviewItem, review_item_id)
        previous_box = item.leitner_box or 1
        target_box = max(1, previous_box - 1) if overall < 50 else previous_box if overall < 70 else min(5, previous_box + 1)
        _apply_box(item, target_box, now=datetime.utcnow())
        session.commit()
        evaluation_id = evaluation.id
    usage = {
        "input_tokens": generation.input_tokens,
        "output_tokens": generation.output_tokens,
        "total_tokens": generation.total_tokens,
    }
    record_token_usage(
        usage=usage,
        feature="written_evaluation",
        subject_id=subject_id,
        provider=generation.provider,
        model=generation.model,
        session_factory=session_factory,
    )
    return {
        "ok": True,
        "evaluation": {
            "id": evaluation_id,
            "overall_score": overall,
            "dimensions": parsed_dimensions,
            "errors": parsed.get("errors") or [],
            "improvements": parsed.get("improvements") or [],
            "example_improvement": parsed.get("example_improvement"),
        },
        "usage": {"available": any(value is not None for value in usage.values()), **usage},
        "student_model": student_model(subject_id=subject_id, session_factory=session_factory),
    }


def professors_overview(*, session_factory=SessionLocal) -> dict[str, Any]:
    with session_factory() as session:
        professors = list(session.scalars(select(Professor).order_by(Professor.name)))
        assignments = list(session.scalars(select(ProfessorAssignment)))
        subjects = {item.id: item.name for item in session.scalars(select(Subject))}
        result = []
        for professor in professors:
            subject_ids = {professor.subject_id}
            subject_ids.update(item.subject_id for item in assignments if item.professor_id == professor.id)
            preference_count = session.scalar(select(func.count(ProfessorPreference.id)).where(ProfessorPreference.professor_id == professor.id)) or 0
            rubric_count = session.scalar(select(func.count(RubricCriterion.id)).where(RubricCriterion.professor_id == professor.id)) or 0
            transcript_count = session.scalar(select(func.count(Document.id)).where(Document.professor_id == professor.id, Document.document_type == "transcript")) or 0
            result.append({
                "id": professor.id,
                "name": professor.name,
                "notes": professor.notes,
                "subjects": [{"id": item, "name": subjects.get(item, "Asignatura")} for item in sorted(subject_ids) if item in subjects],
                "criteria_count": preference_count + rubric_count,
                "transcript_count": transcript_count,
            })
    return {"ok": True, "professors": result}


def assign_professor(
    *, subject_id: int, professor_id: int | None = None, name: str | None = None,
    notes: str | None = None,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    with session_factory() as session:
        subject = session.get(Subject, subject_id)
        if subject is None:
            return {"ok": False, "error": "La asignatura no existe"}
        professor = session.get(Professor, professor_id) if professor_id is not None else None
        if professor_id is not None and professor is None:
            return {"ok": False, "error": "El profesor no existe"}
        if professor is None:
            clean_name = " ".join((name or "").split())
            if not clean_name:
                return {"ok": False, "error": "El nombre es obligatorio"}
            professor = Professor(name=clean_name, subject_id=subject_id, notes=(notes or "").strip() or None)
            session.add(professor)
            session.flush()
        existing = session.scalar(select(ProfessorAssignment).where(
            ProfessorAssignment.professor_id == professor.id,
            ProfessorAssignment.subject_id == subject_id,
        ))
        if existing is None:
            session.add(ProfessorAssignment(professor_id=professor.id, subject_id=subject_id))
        session.commit()
        return {"ok": True, "professor": {"id": professor.id, "name": professor.name, "notes": professor.notes}}


def add_professor_criterion(
    *, professor_id: int, subject_id: int, text_value: str, importance: int,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    clean = " ".join(text_value.split())
    if not clean or importance not in range(1, 6):
        return {"ok": False, "error": "Escribe un criterio y usa importancia entre 1 y 5"}
    with session_factory() as session:
        professor = session.get(Professor, professor_id)
        if professor is None or session.get(Subject, subject_id) is None:
            return {"ok": False, "error": "Profesor o asignatura no disponible"}
        criterion = ProfessorPreference(
            professor_id=professor_id,
            subject_id=subject_id,
            category="analysis",
            preference=clean,
            importance=importance,
            source_type="direct_instruction",
            confidence=5,
        )
        session.add(criterion)
        session.commit()
        return {"ok": True, "criterion": {"id": criterion.id, "preference": clean, "importance": importance, "source_type": criterion.source_type}}


def academic_map(*, session_factory=SessionLocal) -> dict[str, Any]:
    from src.database.models import CurriculumConceptLink, CurriculumItem, GlobalConcept

    with session_factory() as session:
        concepts = list(session.scalars(select(KnowledgeConcept).order_by(KnowledgeConcept.name)))
        subjects = {
            item.id: {"name": item.name, "academic_year": item.academic_year}
            for item in session.scalars(select(Subject))
        }
        connections = list(session.scalars(select(KnowledgeConnection).order_by(KnowledgeConnection.id)))
        by_id = {item.id: item for item in concepts}
        links = list(session.scalars(select(CurriculumConceptLink)))
        curriculum_items = {item.id: item for item in session.scalars(select(CurriculumItem))}
        curriculum_type_by_concept = {
            link.knowledge_concept_id: curriculum_items[link.curriculum_item_id].item_type
            for link in links if link.curriculum_item_id in curriculum_items
        }
        global_concepts = {item.id: item.name for item in session.scalars(select(GlobalConcept))}
    return {
        "ok": True,
        "concepts": [{
            "id": item.id,
            "name": item.name,
            "subject_id": item.subject_id,
            "subject_name": (subjects.get(item.subject_id) or {}).get("name"),
            "academic_year": (subjects.get(item.subject_id) or {}).get("academic_year"),
            "curriculum_type": curriculum_type_by_concept.get(item.id),
            "global_concept": global_concepts.get(item.global_concept_id),
            "mastery": "mastered" if item.status == "strong" else "consolidating" if item.status == "developing" else "not_mastered" if item.status == "weak" else "unassessed",
            "evidence_count": item.evidence_count,
        } for item in concepts],
        "connections": [{
            "id": item.id,
            "source": by_id[item.source_concept_id].name if item.source_concept_id in by_id else "Concepto",
            "target": by_id[item.target_concept_id].name if item.target_concept_id in by_id else "Concepto",
            "relationship": item.relationship,
            "source_type": item.source_type,
        } for item in connections],
        "student_model": student_model(session_factory=session_factory),
    }


def hierarchical_retrieval(
    *,
    query: str,
    subject_id: int,
    include_global: bool,
    retriever: Callable[..., list] = retrieve_ranked_chunks,
) -> dict[str, Any]:
    current_ranked = retriever(query=query, subject_id=subject_id, document_id=None, semantic_weight=0.75)
    current = select_context_chunks(
        ranked_chunks=current_ranked,
        minimum_score=0.20,
        maximum_sources=3,
        maximum_context_characters=3200,
        redundancy_threshold=0.80,
    )
    historical = []
    if include_global:
        global_ranked = retriever(query=query, subject_id=None, document_id=None, semantic_weight=0.75)
        historical_candidates = [item for item in global_ranked if item.document.subject_id != subject_id]
        historical = select_context_chunks(
            ranked_chunks=historical_candidates,
            minimum_score=0.30,
            maximum_sources=2,
            maximum_context_characters=1800,
            redundancy_threshold=0.80,
        )
    return {
        "current": current,
        "historical": historical,
        "global_requested": include_global,
        "source_count": len(current) + len(historical),
    }
