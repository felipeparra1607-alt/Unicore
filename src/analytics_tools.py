from datetime import date, timedelta

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    StudyAttempt,
    StudySession,
    Subject,
)


def safe_average(
    values: list[float],
) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


def calculate_percentage_change(
    previous: float | None,
    current: float | None,
) -> float | None:
    if previous is None or current is None:
        return None

    if previous == 0:
        return None

    return round(
        (
            (current - previous)
            / previous
        )
        * 100,
        2,
    )


def build_learning_analytics(
    subject_id: int | None = None,
    comparison_days: int = 14,
) -> dict:
    """
    Compara dos periodos consecutivos.

    Ejemplo con 14 días:
    - periodo actual: últimos 14 días
    - periodo anterior: 14 días anteriores
    """

    if comparison_days < 7 or comparison_days > 180:
        return {
            "ok": False,
            "error": (
                "comparison_days debe estar "
                "entre 7 y 180"
            ),
        }

    today = date.today()

    current_start = (
        today
        - timedelta(
            days=comparison_days - 1
        )
    )

    previous_end = (
        current_start
        - timedelta(days=1)
    )

    previous_start = (
        previous_end
        - timedelta(
            days=comparison_days - 1
        )
    )

    with SessionLocal() as session:
        subject = None

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

        study_statement = select(
            StudySession
        ).where(
            StudySession.session_date
            >= previous_start,
            StudySession.session_date
            <= today,
        )

        quiz_statement = select(
            StudyAttempt
        ).where(
            StudyAttempt.status
            == "completed"
        )

        task_statement = select(
            AcademicTask
        )

        if subject_id is not None:
            study_statement = (
                study_statement.where(
                    StudySession.subject_id
                    == subject_id
                )
            )

            quiz_statement = (
                quiz_statement.where(
                    StudyAttempt.subject_id
                    == subject_id
                )
            )

            task_statement = (
                task_statement.where(
                    AcademicTask.subject_id
                    == subject_id
                )
            )

        study_sessions = session.scalars(
            study_statement
        ).all()

        quiz_attempts = session.scalars(
            quiz_statement
        ).all()

        tasks = session.scalars(
            task_statement
        ).all()

        current_sessions = [
            item
            for item in study_sessions
            if item.session_date
            >= current_start
        ]

        previous_sessions = [
            item
            for item in study_sessions
            if (
                previous_start
                <= item.session_date
                <= previous_end
            )
        ]

        current_minutes = sum(
            item.duration_minutes
            for item in current_sessions
        )

        previous_minutes = sum(
            item.duration_minutes
            for item in previous_sessions
        )

        current_active_days = len(
            {
                item.session_date
                for item in current_sessions
            }
        )

        previous_active_days = len(
            {
                item.session_date
                for item in previous_sessions
            }
        )

        current_focus = safe_average(
            [
                item.focus_rating
                for item in current_sessions
                if item.focus_rating
                is not None
            ]
        )

        previous_focus = safe_average(
            [
                item.focus_rating
                for item in previous_sessions
                if item.focus_rating
                is not None
            ]
        )

        current_satisfaction = safe_average(
            [
                item.satisfaction_rating
                for item in current_sessions
                if item.satisfaction_rating
                is not None
            ]
        )

        previous_satisfaction = safe_average(
            [
                item.satisfaction_rating
                for item in previous_sessions
                if item.satisfaction_rating
                is not None
            ]
        )

        current_quizzes = [
            item
            for item in quiz_attempts
            if (
                item.completed_at
                and item.completed_at.date()
                >= current_start
                and item.completed_at.date()
                <= today
                and item.score_percentage
                is not None
            )
        ]

        previous_quizzes = [
            item
            for item in quiz_attempts
            if (
                item.completed_at
                and previous_start
                <= item.completed_at.date()
                <= previous_end
                and item.score_percentage
                is not None
            )
        ]

        current_quiz_average = safe_average(
            [
                item.score_percentage
                for item in current_quizzes
            ]
        )

        previous_quiz_average = safe_average(
            [
                item.score_percentage
                for item in previous_quizzes
            ]
        )

        planned_sessions = [
            item
            for item in current_sessions
            if item.planned_minutes
            is not None
        ]

        completed_plans = [
            item
            for item in planned_sessions
            if item.completed_plan
        ]

        plan_completion = (
            len(completed_plans)
            / len(planned_sessions)
            * 100
            if planned_sessions
            else None
        )

        completed_tasks = [
            item
            for item in tasks
            if item.status
            == "completed"
        ]

        tasks_with_estimate = [
            item
            for item in completed_tasks
            if (
                item.estimated_minutes
                is not None
                and item.estimated_minutes > 0
                and item.spent_minutes > 0
            )
        ]

        task_efficiency_values = []

        for task in tasks_with_estimate:
            ratio = (
                task.estimated_minutes
                / task.spent_minutes
                * 100
            )

            task_efficiency_values.append(
                min(
                    ratio,
                    150,
                )
            )

        task_time_efficiency = (
            safe_average(
                task_efficiency_values
            )
        )

        # Índice interno de eficiencia.
        # No pretende medir capacidad académica absoluta.
        efficiency_components = []

        if current_focus is not None:
            efficiency_components.append(
                current_focus / 5 * 100
            )

        if (
            current_quiz_average
            is not None
        ):
            efficiency_components.append(
                current_quiz_average
            )

        if (
            plan_completion
            is not None
        ):
            efficiency_components.append(
                plan_completion
            )

        study_efficiency_index = (
            safe_average(
                efficiency_components
            )
        )

        if (
            study_efficiency_index
            is not None
        ):
            study_efficiency_index = round(
                study_efficiency_index,
                2,
            )

        return {
            "ok": True,
            "subject": (
                {
                    "id": subject.id,
                    "name": subject.name,
                }
                if subject
                else None
            ),
            "periods": {
                "current": {
                    "from": (
                        current_start
                        .isoformat()
                    ),
                    "to": (
                        today.isoformat()
                    ),
                },
                "previous": {
                    "from": (
                        previous_start
                        .isoformat()
                    ),
                    "to": (
                        previous_end
                        .isoformat()
                    ),
                },
            },
            "current": {
                "study_minutes": (
                    current_minutes
                ),
                "active_days": (
                    current_active_days
                ),
                "average_focus": (
                    round(
                        current_focus,
                        2,
                    )
                    if current_focus
                    is not None
                    else None
                ),
                "average_satisfaction": (
                    round(
                        current_satisfaction,
                        2,
                    )
                    if current_satisfaction
                    is not None
                    else None
                ),
                "quiz_average_percentage": (
                    round(
                        current_quiz_average,
                        2,
                    )
                    if current_quiz_average
                    is not None
                    else None
                ),
                "plan_completion_percentage": (
                    round(
                        plan_completion,
                        2,
                    )
                    if plan_completion
                    is not None
                    else None
                ),
                "task_time_efficiency_percentage": (
                    round(
                        task_time_efficiency,
                        2,
                    )
                    if task_time_efficiency
                    is not None
                    else None
                ),
                "study_efficiency_index": (
                    study_efficiency_index
                ),
            },
            "previous": {
                "study_minutes": (
                    previous_minutes
                ),
                "active_days": (
                    previous_active_days
                ),
                "average_focus": (
                    round(
                        previous_focus,
                        2,
                    )
                    if previous_focus
                    is not None
                    else None
                ),
                "average_satisfaction": (
                    round(
                        previous_satisfaction,
                        2,
                    )
                    if previous_satisfaction
                    is not None
                    else None
                ),
                "quiz_average_percentage": (
                    round(
                        previous_quiz_average,
                        2,
                    )
                    if previous_quiz_average
                    is not None
                    else None
                ),
            },
            "trends": {
                "study_minutes_change_percentage": (
                    calculate_percentage_change(
                        previous_minutes,
                        current_minutes,
                    )
                ),
                "active_days_change_percentage": (
                    calculate_percentage_change(
                        previous_active_days,
                        current_active_days,
                    )
                ),
                "focus_change_percentage": (
                    calculate_percentage_change(
                        previous_focus,
                        current_focus,
                    )
                ),
                "quiz_average_change_percentage": (
                    calculate_percentage_change(
                        previous_quiz_average,
                        current_quiz_average,
                    )
                ),
            },
            "interpretation": {
                "study_efficiency_index": (
                    "Índice interno basado en foco, "
                    "quizzes y cumplimiento de "
                    "planificación. No es una "
                    "medida absoluta de rendimiento."
                )
            },
            "provider_called": False,
            "estimated_cost_usd": 0,
        }


def register_analytics_tools(mcp) -> None:

    @mcp.tool()
    def get_learning_analytics(
        subject_id: int | None = None,
        comparison_days: int = 14,
    ) -> dict:
        """
        Devuelve tendencias y métricas
        de eficiencia de estudio.
        """

        return build_learning_analytics(
            subject_id=subject_id,
            comparison_days=comparison_days,
        )