import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    ReviewItem,
    StudyAnswer,
    StudyAttempt,
    Subject,
)


def review_item_to_dict(
    item: ReviewItem,
) -> dict[str, Any]:
    """Convierte un elemento de repaso en un diccionario."""

    return {
        "id": item.id,
        "subject_id": item.subject_id,
        "source_attempt_id": item.source_attempt_id,
        "source_answer_id": item.source_answer_id,
        "topic": item.topic,
        "question": item.question,
        "correct_answer": item.correct_answer,
        "explanation": item.explanation,
        "sources": (
            json.loads(item.sources_json)
            if item.sources_json
            else []
        ),
        "status": item.status,
        "priority": item.priority,
        "repetition_count": item.repetition_count,
        "correct_streak": item.correct_streak,
        "incorrect_count": item.incorrect_count,
        "interval_days": item.interval_days,
        "ease_factor": item.ease_factor,
        "last_reviewed_at": (
            item.last_reviewed_at.isoformat()
            if item.last_reviewed_at
            else None
        ),
        "next_review_at": (
            item.next_review_at.isoformat()
            if item.next_review_at
            else None
        ),
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


def calculate_priority(
    item: ReviewItem,
    now: datetime,
) -> int:
    """
    Calcula prioridad entre 1 y 5.

    5 significa repaso muy urgente.
    1 significa baja prioridad.
    """

    priority = 1

    if item.next_review_at <= now:
        priority += 2

    if item.incorrect_count >= 2:
        priority += 1

    if item.correct_streak == 0:
        priority += 1

    return min(priority, 5)


def calculate_next_interval(
    item: ReviewItem,
    correct: bool,
    confidence: int,
) -> tuple[int, float]:
    """
    Calcula el siguiente intervalo de repaso.

    Es una versión sencilla inspirada en repetición espaciada.
    """

    if not correct:
        return 1, max(
            1.3,
            round(item.ease_factor - 0.20, 2),
        )

    if confidence <= 2:
        return 1, max(
            1.3,
            round(item.ease_factor - 0.10, 2),
        )

    if item.correct_streak == 0:
        interval_days = 1
    elif item.correct_streak == 1:
        interval_days = 3
    elif item.correct_streak == 2:
        interval_days = 7
    else:
        interval_days = max(
            item.interval_days + 1,
            round(
                item.interval_days
                * item.ease_factor
            ),
        )

    ease_change = {
        3: 0.00,
        4: 0.05,
        5: 0.10,
    }.get(confidence, 0.00)

    new_ease = min(
        3.0,
        max(
            1.3,
            round(
                item.ease_factor + ease_change,
                2,
            ),
        ),
    )

    return interval_days, new_ease


def register_review_tools(mcp) -> None:
    """Registra las herramientas de repaso inteligente."""

    @mcp.tool()
    def sync_review_items(
        subject_id: int | None = None,
    ) -> dict:
        """
        Convierte respuestas incorrectas de quizzes
        en elementos de repaso.

        No duplica preguntas ya sincronizadas.
        """

        with SessionLocal() as session:
            answer_statement = (
                select(
                    StudyAnswer,
                    StudyAttempt,
                )
                .join(
                    StudyAttempt,
                    StudyAnswer.attempt_id
                    == StudyAttempt.id,
                )
                .where(
                    StudyAnswer.is_correct.is_(False),
                    StudyAttempt.status == "completed",
                )
            )

            if subject_id is not None:
                subject = session.get(
                    Subject,
                    subject_id,
                )

                if subject is None:
                    return {
                        "ok": False,
                        "error": (
                            "La asignatura no existe"
                        ),
                    }

                answer_statement = (
                    answer_statement.where(
                        StudyAttempt.subject_id
                        == subject_id
                    )
                )

            rows = session.execute(
                answer_statement
            ).all()

            created_count = 0
            existing_count = 0
            created_items = []

            for answer, attempt in rows:
                existing_item = session.scalar(
                    select(ReviewItem).where(
                        ReviewItem.source_answer_id
                        == answer.id
                    )
                )

                if existing_item is not None:
                    existing_count += 1
                    continue

                quiz_data = json.loads(
                    attempt.questions_json
                )

                quiz_items = quiz_data.get(
                    "items",
                    [],
                )

                correct_answer = None

                if (
                    0
                    <= answer.question_index
                    < len(quiz_items)
                ):
                    quiz_item = quiz_items[
                        answer.question_index
                    ]

                    options = quiz_item.get(
                        "options",
                        [],
                    )

                    if (
                        0
                        <= answer.correct_index
                        < len(options)
                    ):
                        correct_answer = options[
                            answer.correct_index
                        ]

                review_item = ReviewItem(
                    subject_id=attempt.subject_id,
                    source_attempt_id=attempt.id,
                    source_answer_id=answer.id,
                    topic=attempt.topic,
                    question=answer.question,
                    correct_answer=correct_answer,
                    explanation=answer.explanation,
                    sources_json=answer.sources_json,
                    status="learning",
                    priority=5,
                    repetition_count=0,
                    correct_streak=0,
                    incorrect_count=1,
                    interval_days=1,
                    ease_factor=2.5,
                    next_review_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )

                session.add(review_item)
                session.flush()

                created_count += 1

                created_items.append(
                    review_item_to_dict(
                        review_item
                    )
                )

            session.commit()

            return {
                "ok": True,
                "incorrect_answers_found": len(rows),
                "created_count": created_count,
                "already_existing_count": (
                    existing_count
                ),
                "created_items": created_items,
            }

    @mcp.tool()
    def list_review_items(
        subject_id: int | None = None,
        status: str | None = None,
        due_only: bool = False,
        maximum_results: int = 50,
    ) -> dict:
        """Lista elementos de repaso con filtros."""

        if (
            maximum_results < 1
            or maximum_results > 200
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_results debe estar "
                    "entre 1 y 200"
                ),
            }

        clean_status = None

        if status is not None:
            clean_status = (
                status.strip().casefold()
            )

            if clean_status not in {
                "learning",
                "reviewing",
                "mastered",
            }:
                return {
                    "ok": False,
                    "error": (
                        "status debe ser learning, "
                        "reviewing o mastered"
                    ),
                }

        now = datetime.utcnow()

        with SessionLocal() as session:
            statement = select(
                ReviewItem
            )

            if subject_id is not None:
                statement = statement.where(
                    ReviewItem.subject_id
                    == subject_id
                )

            if clean_status is not None:
                statement = statement.where(
                    ReviewItem.status
                    == clean_status
                )

            if due_only:
                statement = statement.where(
                    ReviewItem.next_review_at
                    <= now,
                    ReviewItem.status
                    != "mastered",
                )

            statement = statement.order_by(
                ReviewItem.priority.desc(),
                ReviewItem.next_review_at.asc(),
                ReviewItem.id.asc(),
            ).limit(maximum_results)

            items = session.scalars(
                statement
            ).all()

            for item in items:
                item.priority = calculate_priority(
                    item,
                    now,
                )

            session.commit()

            return {
                "ok": True,
                "result_count": len(items),
                "due_only": due_only,
                "items": [
                    review_item_to_dict(item)
                    for item in items
                ],
            }

    @mcp.tool()
    def get_review_plan(
        subject_id: int,
        maximum_items: int = 10,
    ) -> dict:
        """
        Genera el plan de repaso actual de una asignatura.
        """

        if (
            maximum_items < 1
            or maximum_items > 50
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_items debe estar "
                    "entre 1 y 50"
                ),
            }

        now = datetime.utcnow()

        with SessionLocal() as session:
            subject = session.get(
                Subject,
                subject_id,
            )

            if subject is None:
                return {
                    "ok": False,
                    "error": (
                        "La asignatura no existe"
                    ),
                }

            all_items = session.scalars(
                select(ReviewItem)
                .where(
                    ReviewItem.subject_id
                    == subject_id
                )
                .order_by(
                    ReviewItem.next_review_at.asc(),
                    ReviewItem.priority.desc(),
                )
            ).all()

            due_items = [
                item
                for item in all_items
                if (
                    item.status != "mastered"
                    and item.next_review_at <= now
                )
            ]

            upcoming_items = [
                item
                for item in all_items
                if (
                    item.status != "mastered"
                    and item.next_review_at > now
                )
            ]

            mastered_items = [
                item
                for item in all_items
                if item.status == "mastered"
            ]

            for item in due_items:
                item.priority = calculate_priority(
                    item,
                    now,
                )

            due_items.sort(
                key=lambda item: (
                    -item.priority,
                    item.next_review_at,
                    item.id,
                )
            )

            selected_items = due_items[
                :maximum_items
            ]

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "summary": {
                    "total_items": len(
                        all_items
                    ),
                    "due_now": len(
                        due_items
                    ),
                    "upcoming": len(
                        upcoming_items
                    ),
                    "mastered": len(
                        mastered_items
                    ),
                },
                "recommended_session_size": len(
                    selected_items
                ),
                "recommended_items": [
                    review_item_to_dict(item)
                    for item in selected_items
                ],
                "message": (
                    "No tienes repasos pendientes."
                    if not selected_items
                    else (
                        "Empieza por los elementos "
                        "con prioridad más alta."
                    )
                ),
            }

    @mcp.tool()
    def submit_review_result(
        review_item_id: int,
        correct: bool,
        confidence: int,
    ) -> dict:
        """
        Registra el resultado de un repaso.

        confidence debe estar entre 1 y 5:
        1 = no lo recordaba;
        3 = lo recordaba con dificultad;
        5 = lo recordaba perfectamente.
        """

        if confidence < 1 or confidence > 5:
            return {
                "ok": False,
                "error": (
                    "confidence debe estar "
                    "entre 1 y 5"
                ),
            }

        now = datetime.utcnow()

        with SessionLocal() as session:
            item = session.get(
                ReviewItem,
                review_item_id,
            )

            if item is None:
                return {
                    "ok": False,
                    "error": (
                        "El elemento de repaso no existe"
                    ),
                }

            previous_state = {
                "status": item.status,
                "correct_streak": (
                    item.correct_streak
                ),
                "interval_days": (
                    item.interval_days
                ),
                "ease_factor": item.ease_factor,
                "next_review_at": (
                    item.next_review_at.isoformat()
                ),
            }

            item.repetition_count += 1
            item.last_reviewed_at = now

            if correct:
                item.correct_streak += 1
            else:
                item.correct_streak = 0
                item.incorrect_count += 1

            interval_days, new_ease = (
                calculate_next_interval(
                    item=item,
                    correct=correct,
                    confidence=confidence,
                )
            )

            item.interval_days = interval_days
            item.ease_factor = new_ease
            item.next_review_at = (
                now
                + timedelta(
                    days=interval_days
                )
            )

            if (
                correct
                and item.correct_streak >= 3
                and confidence >= 4
            ):
                item.status = "mastered"
            elif correct:
                item.status = "reviewing"
            else:
                item.status = "learning"

            item.priority = calculate_priority(
                item,
                now,
            )

            item.updated_at = now

            session.commit()
            session.refresh(item)

            return {
                "ok": True,
                "result": {
                    "correct": correct,
                    "confidence": confidence,
                },
                "previous_state": previous_state,
                "review_item": review_item_to_dict(
                    item
                ),
                "interpretation": (
                    "El elemento se considera dominado."
                    if item.status == "mastered"
                    else (
                        "El elemento volverá a repasarse "
                        f"en {item.interval_days} día(s)."
                    )
                ),
            }