from datetime import date, datetime, timedelta

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    Assessment,
    ReviewItem,
    StudyAttempt,
    StudySession,
    Subject,
)


def calculate_risk_level(
    score: int,
) -> str:
    if score >= 70:
        return "high"

    if score >= 40:
        return "medium"

    return "low"


def build_subject_risk(
    subject_id: int,
) -> dict:
    """
    Calcula señales de riesgo académico.

    No predice suspensos.
    Solo prioriza señales que merecen atención.
    """

    today = date.today()

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

        tasks = session.scalars(
            select(AcademicTask).where(
                AcademicTask.subject_id
                == subject_id,
                AcademicTask.status.notin_(
                    ["completed", "cancelled"]
                ),
            )
        ).all()

        assessments = session.scalars(
            select(Assessment).where(
                Assessment.subject_id
                == subject_id,
                Assessment.status
                == "pending",
            )
        ).all()

        reviews = session.scalars(
            select(ReviewItem).where(
                ReviewItem.subject_id
                == subject_id,
                ReviewItem.status
                != "mastered",
            )
        ).all()

        attempts = session.scalars(
            select(StudyAttempt).where(
                StudyAttempt.subject_id
                == subject_id,
                StudyAttempt.status
                == "completed",
            )
        ).all()

        study_sessions = session.scalars(
            select(StudySession).where(
                StudySession.subject_id
                == subject_id
            )
        ).all()

        risk_score = 0
        signals = []

        overdue_tasks = [
            item
            for item in tasks
            if (
                item.due_date
                and item.due_date < today
            )
        ]

        if overdue_tasks:
            points = min(
                30,
                15
                + (
                    len(overdue_tasks) - 1
                )
                * 5,
            )

            risk_score += points

            signals.append({
                "type": "overdue_tasks",
                "severity": "high",
                "points": points,
                "message": (
                    f"Hay {len(overdue_tasks)} "
                    "tarea(s) vencida(s)."
                ),
            })

        urgent_tasks = [
            item
            for item in tasks
            if (
                item.due_date
                and 0
                <= (
                    item.due_date
                    - today
                ).days
                <= 3
            )
        ]

        if urgent_tasks:
            points = min(
                20,
                len(urgent_tasks)
                * 7,
            )

            risk_score += points

            signals.append({
                "type": "urgent_tasks",
                "severity": "medium",
                "points": points,
                "message": (
                    f"Hay {len(urgent_tasks)} "
                    "tarea(s) que vencen "
                    "en 3 días o menos."
                ),
            })

        future_assessments = [
            item
            for item in assessments
            if (
                item.assessment_date
                is not None
                and item.assessment_date
                >= today
            )
        ]

        future_assessments.sort(
            key=lambda item: (
                item.assessment_date
            )
        )

        next_assessment = (
            future_assessments[0]
            if future_assessments
            else None
        )

        if next_assessment:
            days = (
                next_assessment
                .assessment_date
                - today
            ).days

            if days <= 7:
                risk_score += 15

                signals.append({
                    "type": (
                        "assessment_soon"
                    ),
                    "severity": "medium",
                    "points": 15,
                    "message": (
                        f"{next_assessment.title} "
                        f"es en {days} día(s)."
                    ),
                })

        due_reviews = [
            item
            for item in reviews
            if item.next_review_at
            <= datetime.utcnow()
        ]

        if due_reviews:
            points = min(
                15,
                len(due_reviews)
                * 3,
            )

            risk_score += points

            signals.append({
                "type": "due_reviews",
                "severity": "medium",
                "points": points,
                "message": (
                    f"Hay {len(due_reviews)} "
                    "repaso(s) pendientes."
                ),
            })

        quiz_scores = [
            item.score_percentage
            for item in attempts[-5:]
            if item.score_percentage
            is not None
        ]

        quiz_average = (
            sum(quiz_scores)
            / len(quiz_scores)
            if quiz_scores
            else None
        )

        if (
            quiz_average is not None
            and quiz_average < 60
        ):
            risk_score += 20

            signals.append({
                "type": (
                    "low_quiz_performance"
                ),
                "severity": "high",
                "points": 20,
                "message": (
                    "La media reciente de quizzes "
                    f"es {quiz_average:.1f} %."
                ),
            })

        recent_start = (
            today - timedelta(days=6)
        )

        recent_minutes = sum(
            item.duration_minutes
            for item in study_sessions
            if (
                recent_start
                <= item.session_date
                <= today
            )
        )

        if (
            next_assessment is not None
            and (
                next_assessment
                .assessment_date
                - today
            ).days
            <= 14
            and recent_minutes < 60
        ):
            risk_score += 15

            signals.append({
                "type": (
                    "low_recent_preparation"
                ),
                "severity": "medium",
                "points": 15,
                "message": (
                    "Hay una evaluación próxima "
                    "y menos de 60 minutos de "
                    "estudio registrados esta semana."
                ),
            })

        risk_score = min(
            risk_score,
            100,
        )

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            },
            "risk": {
                "score": risk_score,
                "level": (
                    calculate_risk_level(
                        risk_score
                    )
                ),
            },
            "signals": sorted(
                signals,
                key=lambda item: (
                    item["points"]
                ),
                reverse=True,
            ),
            "metrics": {
                "overdue_task_count": (
                    len(overdue_tasks)
                ),
                "urgent_task_count": (
                    len(urgent_tasks)
                ),
                "due_review_count": (
                    len(due_reviews)
                ),
                "recent_quiz_average": (
                    round(
                        quiz_average,
                        2,
                    )
                    if quiz_average
                    is not None
                    else None
                ),
                "study_minutes_last_7_days": (
                    recent_minutes
                ),
            },
            "next_assessment": (
                {
                    "id": (
                        next_assessment.id
                    ),
                    "title": (
                        next_assessment.title
                    ),
                    "date": (
                        next_assessment
                        .assessment_date
                        .isoformat()
                    ),
                    "days_remaining": (
                        next_assessment
                        .assessment_date
                        - today
                    ).days,
                }
                if next_assessment
                else None
            ),
            "note": (
                "El riesgo es una señal interna "
                "de priorización y no una predicción "
                "de aprobar o suspender."
            ),
            "provider_called": False,
            "estimated_cost_usd": 0,
        }


def register_academic_risk_tools(mcp) -> None:

    @mcp.tool()
    def get_subject_academic_risk(
        subject_id: int,
    ) -> dict:
        """Calcula el riesgo de una asignatura."""

        return build_subject_risk(
            subject_id
        )

    @mcp.tool()
    def get_academic_risk_overview() -> dict:
        """
        Ordena todas las asignaturas
        según atención necesaria.
        """

        with SessionLocal() as session:
            subjects = session.scalars(
                select(Subject).order_by(
                    Subject.name.asc()
                )
            ).all()

        results = []

        for subject in subjects:
            result = build_subject_risk(
                subject.id
            )

            if result.get("ok"):
                results.append(
                    result
                )

        results.sort(
            key=lambda item: (
                item["risk"]["score"]
            ),
            reverse=True,
        )

        return {
            "ok": True,
            "subject_count": len(
                results
            ),
            "high_risk_count": sum(
                1
                for item in results
                if (
                    item["risk"]["level"]
                    == "high"
                )
            ),
            "medium_risk_count": sum(
                1
                for item in results
                if (
                    item["risk"]["level"]
                    == "medium"
                )
            ),
            "low_risk_count": sum(
                1
                for item in results
                if (
                    item["risk"]["level"]
                    == "low"
                )
            ),
            "subjects": results,
            "provider_called": False,
            "estimated_cost_usd": 0,
        }