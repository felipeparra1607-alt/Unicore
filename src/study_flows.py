from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import ReviewItem, Subject
from src.review_tools import review_item_to_dict


def _source_matches_document(sources_json: str | None, document_id: int | None) -> bool:
    if document_id is None:
        return True
    try:
        sources = json.loads(sources_json or "[]")
    except json.JSONDecodeError:
        return False
    return any(isinstance(item, dict) and item.get("document_id") == document_id for item in sources)


def reusable_flashcards(
    *,
    subject_id: int,
    topic: str,
    document_id: int | None = None,
    maximum_items: int = 10,
    session_factory=SessionLocal,
) -> list[dict[str, Any]]:
    clean_topic = " ".join(topic.split()).casefold()
    with session_factory() as session:
        items = list(
            session.scalars(
                select(ReviewItem)
                .where(
                    ReviewItem.subject_id == subject_id,
                    ReviewItem.source_attempt_id.is_(None),
                    ReviewItem.source_answer_id.is_(None),
                    ReviewItem.correct_answer.is_not(None),
                )
                .order_by(ReviewItem.id)
            )
        )
        return [
            review_item_to_dict(item)
            for item in items
            if " ".join(item.topic.split()).casefold() == clean_topic
            and _source_matches_document(item.sources_json, document_id)
        ][:maximum_items]


def persist_flashcards(
    *,
    subject_id: int,
    topic: str,
    cards: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    document_id: int | None = None,
    session_factory=SessionLocal,
) -> dict[str, Any]:
    """Persiste un lote generado en el sistema de repaso existente."""

    clean_topic = " ".join(topic.split())
    if not clean_topic:
        return {"ok": False, "error": "El tema no puede estar vacío"}
    if not 1 <= len(cards) <= 10:
        return {"ok": False, "error": "El lote debe contener entre 1 y 10 flashcards"}

    existing = reusable_flashcards(
        subject_id=subject_id,
        topic=clean_topic,
        document_id=document_id,
        maximum_items=10,
        session_factory=session_factory,
    )
    if existing:
        return {"ok": True, "reused": True, "cards": existing}

    with session_factory() as session:
        if session.get(Subject, subject_id) is None:
            return {"ok": False, "error": "La asignatura no existe"}
        created = []
        for card in cards:
            front = " ".join(str(card.get("front", "")).split())
            back = " ".join(str(card.get("back", "")).split())
            if not front or not back:
                return {"ok": False, "error": "Cada flashcard necesita pregunta y respuesta"}
            item = ReviewItem(
                subject_id=subject_id,
                topic=clean_topic,
                question=front,
                correct_answer=back,
                explanation=None,
                sources_json=json.dumps(sources, ensure_ascii=False),
                status="learning",
                priority=3,
                repetition_count=0,
                correct_streak=0,
                incorrect_count=0,
                interval_days=1,
                ease_factor=2.5,
                next_review_at=datetime.utcnow(),
            )
            session.add(item)
            session.flush()
            created.append(review_item_to_dict(item))
        session.commit()
        return {"ok": True, "reused": False, "cards": created}
