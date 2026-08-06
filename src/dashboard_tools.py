import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from src.database.connection import SessionLocal
from src.database.models import (
    ClassSession,
    ReviewItem,
    StudyAttempt,
    Subject,
)


def datetime_to_text(
    value: datetime | None,
) -> str | None:
    """Convierte una fecha y hora en texto ISO."""

    return value.isoformat() if value else None


def class_session_summary(
    class_session: ClassSession | None,
) -> dict[str, Any] | None:
    """Resume una sesión de clase."""

    if class_session is None:
        return None

    return {
        "id": class_session.id,
        "title": class_session.title,
        "class_date": (
            class_session.class_date.isoformat()
            if class_session.class_date
            else None
        ),
        "start_time": class_session.start_time,
        "session_type": class_session.session_type,
        "attended": class_session.attended,
        "topics": class_session.topics,
        "summary": class_session.summary,
        "doubts": class_session.doubts,
        "tasks": class_session.tasks,
    }


def attempt_summary(
    attempt: StudyAttempt,
) -> dict[str, Any]:
    """Resume un intento de estudio."""

    return {
        "id": attempt.id,
        "topic": attempt.topic,
        "study_mode": attempt.study_mode,
        "difficulty": attempt.difficulty,
        "total_questions": attempt.total_questions,
        "correct_answers": attempt.correct_answers,
        "score_percentage": attempt.score_percentage,
        "status": attempt.status,
        "started_at": datetime_to_text(
            attempt.started_at
        ),
        "completed_at": datetime_to_text(
            attempt.completed_at
        ),
    }


def review_summary(
    item: ReviewItem,
) -> dict[str, Any]:
    """Resume un elemento de repaso."""

    return {
        "id": item.id,
        "topic": item.topic,
        "question": item.question,
        "correct_answer": item.correct_answer,
        "status": item.status,
        "priority": item.priority,
        "correct_streak": item.correct_streak,
        "incorrect_count": item.incorrect_count,
        "interval_days": item.interval_days,
        "next_review_at": datetime_to_text(
            item.next_review_at
        ),
    }


def collect_weak_topics(
    attempts: list[StudyAttempt],
    maximum_results: int = 10,
) -> list[dict[str, Any]]:
    """Recopila las preguntas falladas más recientes."""

    weak_topics = []

    for attempt in attempts:
        if not attempt.results_json:
            continue

        try:
            results = json.loads(
                attempt.results_json
            )
        except json.JSONDecodeError:
            continue

        for question in results.get(
            "weak_topics",
            [],
        ):
            weak_topics.append({
                "attempt_id": attempt.id,
                "topic": attempt.topic,
                "question": question,
                "completed_at": datetime_to_text(
                    attempt.completed_at
                ),
            })

            if len(weak_topics) >= maximum_results:
                return weak_topics

    return weak_topics


def register_dashboard_tools(mcp) -> None:
    """Registra las herramientas del panel académico."""

    @mcp.tool()
    def get_subject_dashboard(
        subject_id: int,
        recent_attempt_limit: int = 5,
        weak_topic_limit: int = 10,
    ) -> dict:
        """
        Devuelve una visión general de una asignatura.

        Incluye clases, puntuaciones, errores y repasos.
        """

        if (
            recent_attempt_limit < 1
            or recent_attempt_limit > 50
        ):
            return {
                "ok": False,
                "error": (
                    "recent_attempt_limit debe estar "
                    "entre 1 y 50"
                ),
            }

        if (
            weak_topic_limit < 1
            or weak_topic_limit > 50
        ):
            return {
                "ok": False,
                "error": (
                    "weak_topic_limit debe estar "
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

            completed_attempts = session.scalars(
                select(StudyAttempt)
                .where(
                    StudyAttempt.subject_id
                    == subject_id,
                    StudyAttempt.status
                    == "completed",
                )
                .order_by(
                    StudyAttempt.completed_at.desc(),
                    StudyAttempt.id.desc(),
                )
            ).all()

            pending_attempts = session.scalars(
                select(StudyAttempt)
                .where(
                    StudyAttempt.subject_id
                    == subject_id,
                    StudyAttempt.status
                    == "pending",
                )
                .order_by(
                    StudyAttempt.started_at.desc(),
                    StudyAttempt.id.desc(),
                )
            ).all()

            latest_class = session.scalar(
                select(ClassSession)
                .where(
                    ClassSession.subject_id
                    == subject_id
                )
                .order_by(
                    ClassSession.class_date.desc(),
                    ClassSession.start_time.desc(),
                    ClassSession.id.desc(),
                )
                .limit(1)
            )

            total_classes = session.scalar(
                select(
                    func.count(
                        ClassSession.id
                    )
                ).where(
                    ClassSession.subject_id
                    == subject_id
                )
            ) or 0

            attended_classes = session.scalar(
                select(
                    func.count(
                        ClassSession.id
                    )
                ).where(
                    ClassSession.subject_id
                    == subject_id,
                    ClassSession.attended.is_(True),
                )
            ) or 0

            all_review_items = session.scalars(
                select(ReviewItem)
                .where(
                    ReviewItem.subject_id
                    == subject_id
                )
                .order_by(
                    ReviewItem.priority.desc(),
                    ReviewItem.next_review_at.asc(),
                )
            ).all()

            due_review_items = [
                item
                for item in all_review_items
                if (
                    item.status != "mastered"
                    and item.next_review_at <= now
                )
            ]

            upcoming_review_items = [
                item
                for item in all_review_items
                if (
                    item.status != "mastered"
                    and item.next_review_at > now
                )
            ]

            mastered_review_items = [
                item
                for item in all_review_items
                if item.status == "mastered"
            ]

            total_questions = sum(
                attempt.total_questions
                for attempt in completed_attempts
            )

            total_correct = sum(
                attempt.correct_answers or 0
                for attempt in completed_attempts
            )

            overall_score = (
                round(
                    total_correct
                    / total_questions
                    * 100,
                    2,
                )
                if total_questions > 0
                else None
            )

            average_attempt_score = (
                round(
                    sum(
                        attempt.score_percentage or 0
                        for attempt in completed_attempts
                    )
                    / len(completed_attempts),
                    2,
                )
                if completed_attempts
                else None
            )

            attendance_percentage = (
                round(
                    attended_classes
                    / total_classes
                    * 100,
                    2,
                )
                if total_classes > 0
                else None
            )

            weak_topics = collect_weak_topics(
                attempts=completed_attempts,
                maximum_results=weak_topic_limit,
            )

            if due_review_items:
                recommended_action = (
                    "Completa primero los repasos pendientes."
                )
            elif pending_attempts:
                recommended_action = (
                    "Termina el quiz que todavía está pendiente."
                )
            elif weak_topics:
                recommended_action = (
                    "Genera un nuevo quiz sobre tus puntos débiles."
                )
            elif completed_attempts:
                recommended_action = (
                    "Continúa con un tema nuevo o realiza "
                    "un repaso general."
                )
            else:
                recommended_action = (
                    "Genera tu primer material de estudio."
                )

            return {
                "ok": True,
                "generated_at": now.isoformat(),
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                    "academic_year": (
                        subject.academic_year
                    ),
                    "description": (
                        subject.description
                    ),
                },
                "classes": {
                    "total": total_classes,
                    "attended": attended_classes,
                    "attendance_percentage": (
                        attendance_percentage
                    ),
                    "latest_class": (
                        class_session_summary(
                            latest_class
                        )
                    ),
                },
                "study_progress": {
                    "completed_attempts": len(
                        completed_attempts
                    ),
                    "pending_attempts": len(
                        pending_attempts
                    ),
                    "total_questions": (
                        total_questions
                    ),
                    "total_correct": total_correct,
                    "overall_score_percentage": (
                        overall_score
                    ),
                    "average_attempt_score": (
                        average_attempt_score
                    ),
                    "recent_attempts": [
                        attempt_summary(
                            attempt
                        )
                        for attempt
                        in completed_attempts[
                            :recent_attempt_limit
                        ]
                    ],
                },
                "reviews": {
                    "total": len(
                        all_review_items
                    ),
                    "due_now": len(
                        due_review_items
                    ),
                    "upcoming": len(
                        upcoming_review_items
                    ),
                    "mastered": len(
                        mastered_review_items
                    ),
                    "due_items": [
                        review_summary(item)
                        for item
                        in due_review_items[:10]
                    ],
                    "next_upcoming_item": (
                        review_summary(
                            upcoming_review_items[0]
                        )
                        if upcoming_review_items
                        else None
                    ),
                },
                "weak_topics": weak_topics,
                "recommended_action": (
                    recommended_action
                ),
            }

    @mcp.tool()
    def get_daily_study_plan(
        subject_id: int,
        available_minutes: int = 30,
        maximum_review_items: int = 10,
    ) -> dict:
        """
        Crea un plan de estudio local para la sesión actual.

        No llama a ningún modelo.
        """

        if (
            available_minutes < 5
            or available_minutes > 480
        ):
            return {
                "ok": False,
                "error": (
                    "available_minutes debe estar "
                    "entre 5 y 480"
                ),
            }

        if (
            maximum_review_items < 1
            or maximum_review_items > 50
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_review_items debe estar "
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

            due_reviews = session.scalars(
                select(ReviewItem)
                .where(
                    ReviewItem.subject_id
                    == subject_id,
                    ReviewItem.status
                    != "mastered",
                    ReviewItem.next_review_at
                    <= now,
                )
                .order_by(
                    ReviewItem.priority.desc(),
                    ReviewItem.next_review_at.asc(),
                )
                .limit(maximum_review_items)
            ).all()

            pending_attempts = session.scalars(
                select(StudyAttempt)
                .where(
                    StudyAttempt.subject_id
                    == subject_id,
                    StudyAttempt.status
                    == "pending",
                )
                .order_by(
                    StudyAttempt.started_at.asc()
                )
            ).all()

            completed_attempts = session.scalars(
                select(StudyAttempt)
                .where(
                    StudyAttempt.subject_id
                    == subject_id,
                    StudyAttempt.status
                    == "completed",
                )
                .order_by(
                    StudyAttempt.completed_at.desc()
                )
            ).all()

            weak_topics = collect_weak_topics(
                attempts=completed_attempts,
                maximum_results=5,
            )

            remaining_minutes = (
                available_minutes
            )

            plan_steps = []

            if due_reviews and remaining_minutes >= 5:
                review_minutes = min(
                    remaining_minutes,
                    max(
                        5,
                        len(due_reviews) * 3,
                    ),
                )

                plan_steps.append({
                    "order": len(plan_steps) + 1,
                    "action": "review_due_items",
                    "title": (
                        "Repasar errores pendientes"
                    ),
                    "minutes": review_minutes,
                    "item_count": len(
                        due_reviews
                    ),
                    "items": [
                        review_summary(item)
                        for item in due_reviews
                    ],
                })

                remaining_minutes -= review_minutes

            if (
                pending_attempts
                and remaining_minutes >= 5
            ):
                quiz_minutes = min(
                    remaining_minutes,
                    10,
                )

                plan_steps.append({
                    "order": len(plan_steps) + 1,
                    "action": (
                        "complete_pending_quiz"
                    ),
                    "title": (
                        "Terminar el quiz pendiente"
                    ),
                    "minutes": quiz_minutes,
                    "attempt": attempt_summary(
                        pending_attempts[0]
                    ),
                })

                remaining_minutes -= quiz_minutes

            if (
                weak_topics
                and remaining_minutes >= 10
            ):
                weak_topic_minutes = min(
                    remaining_minutes,
                    15,
                )

                plan_steps.append({
                    "order": len(plan_steps) + 1,
                    "action": (
                        "study_weak_topics"
                    ),
                    "title": (
                        "Revisar puntos débiles"
                    ),
                    "minutes": weak_topic_minutes,
                    "topics": weak_topics[:3],
                })

                remaining_minutes -= (
                    weak_topic_minutes
                )

            if remaining_minutes >= 5:
                plan_steps.append({
                    "order": len(plan_steps) + 1,
                    "action": "new_study_material",
                    "title": (
                        "Estudiar o practicar un tema nuevo"
                    ),
                    "minutes": remaining_minutes,
                    "suggested_modes": [
                        "quick_review",
                        "quiz",
                        "flashcards",
                    ],
                })

                remaining_minutes = 0

            if not plan_steps:
                plan_steps.append({
                    "order": 1,
                    "action": "quick_review",
                    "title": "Realizar un repaso breve",
                    "minutes": available_minutes,
                })

            return {
                "ok": True,
                "generated_at": now.isoformat(),
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "available_minutes": (
                    available_minutes
                ),
                "planned_minutes": sum(
                    step["minutes"]
                    for step in plan_steps
                ),
                "due_review_count": len(
                    due_reviews
                ),
                "pending_attempt_count": len(
                    pending_attempts
                ),
                "weak_topic_count": len(
                    weak_topics
                ),
                "steps": plan_steps,
                "provider_called": False,
                "estimated_cost_usd": 0,
            }