from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    StudySession,
    Subject,
)


ALLOWED_ACTIVITY_TYPES = {
    "quiz",
    "flashcards",
    "quick_review",
    "summary",
    "explanation",
    "reading",
    "class_notes",
    "project",
    "other",
}


def clean_optional_text(
    value: str | None,
) -> str | None:
    """Limpia un texto opcional."""

    if value is None:
        return None

    cleaned = value.strip()

    return cleaned or None


def parse_session_date(
    value: str | None,
) -> date:
    """Convierte YYYY-MM-DD en fecha."""

    if value is None or not value.strip():
        return date.today()

    return date.fromisoformat(
        value.strip()
    )


def parse_optional_datetime(
    value: str | None,
) -> datetime | None:
    """Convierte una fecha y hora ISO opcional."""

    if value is None or not value.strip():
        return None

    return datetime.fromisoformat(
        value.strip()
    )


def validate_rating(
    value: int | None,
    field_name: str,
) -> int | None:
    """Valida una puntuación de 1 a 5."""

    if value is None:
        return None

    if value < 1 or value > 5:
        raise ValueError(
            f"{field_name} debe estar entre 1 y 5"
        )

    return value


def study_session_to_dict(
    study_session: StudySession,
    subject_name: str | None = None,
) -> dict[str, Any]:
    """Convierte una sesión de estudio en un diccionario."""

    return {
        "id": study_session.id,
        "subject_id": study_session.subject_id,
        "subject_name": subject_name,
        "session_date": (
            study_session.session_date.isoformat()
        ),
        "started_at": (
            study_session.started_at.isoformat()
            if study_session.started_at
            else None
        ),
        "completed_at": (
            study_session.completed_at.isoformat()
            if study_session.completed_at
            else None
        ),
        "duration_minutes": (
            study_session.duration_minutes
        ),
        "activity_type": (
            study_session.activity_type
        ),
        "topic": study_session.topic,
        "notes": study_session.notes,
        "planned_minutes": (
            study_session.planned_minutes
        ),
        "completed_plan": (
            study_session.completed_plan
        ),
        "focus_rating": (
            study_session.focus_rating
        ),
        "difficulty_rating": (
            study_session.difficulty_rating
        ),
        "satisfaction_rating": (
            study_session.satisfaction_rating
        ),
        "created_at": (
            study_session.created_at.isoformat()
            if study_session.created_at
            else None
        ),
        "updated_at": (
            study_session.updated_at.isoformat()
            if study_session.updated_at
            else None
        ),
    }


def calculate_streaks(
    active_dates: list[date],
    today: date,
) -> dict[str, int]:
    """Calcula la racha actual y la racha máxima."""

    if not active_dates:
        return {
            "current_streak_days": 0,
            "longest_streak_days": 0,
        }

    unique_dates = sorted(
        set(active_dates)
    )

    longest_streak = 1
    running_streak = 1

    for previous_date, current_date in zip(
        unique_dates,
        unique_dates[1:],
    ):
        if (
            current_date - previous_date
            == timedelta(days=1)
        ):
            running_streak += 1
            longest_streak = max(
                longest_streak,
                running_streak,
            )
        else:
            running_streak = 1

    active_date_set = set(unique_dates)

    if today in active_date_set:
        streak_cursor = today
    elif (
        today - timedelta(days=1)
        in active_date_set
    ):
        streak_cursor = (
            today - timedelta(days=1)
        )
    else:
        return {
            "current_streak_days": 0,
            "longest_streak_days": (
                longest_streak
            ),
        }

    current_streak = 0

    while streak_cursor in active_date_set:
        current_streak += 1
        streak_cursor -= timedelta(days=1)

    return {
        "current_streak_days": current_streak,
        "longest_streak_days": longest_streak,
    }


def register_study_session_tools(mcp) -> None:
    """Registra sesiones de estudio y estadísticas."""

    @mcp.tool()
    def create_study_session(
        subject_id: int,
        duration_minutes: int,
        activity_type: str,
        session_date: str | None = None,
        topic: str | None = None,
        notes: str | None = None,
        planned_minutes: int | None = None,
        completed_plan: bool = False,
        focus_rating: int | None = None,
        difficulty_rating: int | None = None,
        satisfaction_rating: int | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict:
        """Guarda una sesión real de estudio."""

        if duration_minutes < 1 or duration_minutes > 1440:
            return {
                "ok": False,
                "error": (
                    "duration_minutes debe estar "
                    "entre 1 y 1440"
                ),
            }

        if (
            planned_minutes is not None
            and (
                planned_minutes < 1
                or planned_minutes > 1440
            )
        ):
            return {
                "ok": False,
                "error": (
                    "planned_minutes debe estar "
                    "entre 1 y 1440"
                ),
            }

        clean_activity_type = (
            activity_type.strip().casefold()
        )

        if clean_activity_type not in ALLOWED_ACTIVITY_TYPES:
            return {
                "ok": False,
                "error": (
                    "activity_type no compatible. "
                    "Usa quiz, flashcards, quick_review, "
                    "summary, explanation, reading, "
                    "class_notes, project u other"
                ),
            }

        try:
            parsed_session_date = (
                parse_session_date(
                    session_date
                )
            )

            parsed_started_at = (
                parse_optional_datetime(
                    started_at
                )
            )

            parsed_completed_at = (
                parse_optional_datetime(
                    completed_at
                )
            )

            parsed_focus_rating = (
                validate_rating(
                    focus_rating,
                    "focus_rating",
                )
            )

            parsed_difficulty_rating = (
                validate_rating(
                    difficulty_rating,
                    "difficulty_rating",
                )
            )

            parsed_satisfaction_rating = (
                validate_rating(
                    satisfaction_rating,
                    "satisfaction_rating",
                )
            )

        except ValueError as error:
            return {
                "ok": False,
                "error": str(error),
            }

        if (
            parsed_started_at
            and parsed_completed_at
            and parsed_completed_at
            < parsed_started_at
        ):
            return {
                "ok": False,
                "error": (
                    "completed_at no puede ser "
                    "anterior a started_at"
                ),
            }

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

            study_session = StudySession(
                subject_id=subject_id,
                session_date=(
                    parsed_session_date
                ),
                started_at=parsed_started_at,
                completed_at=parsed_completed_at,
                duration_minutes=duration_minutes,
                activity_type=(
                    clean_activity_type
                ),
                topic=clean_optional_text(topic),
                notes=clean_optional_text(notes),
                planned_minutes=planned_minutes,
                completed_plan=completed_plan,
                focus_rating=(
                    parsed_focus_rating
                ),
                difficulty_rating=(
                    parsed_difficulty_rating
                ),
                satisfaction_rating=(
                    parsed_satisfaction_rating
                ),
                updated_at=datetime.utcnow(),
            )

            session.add(study_session)
            session.commit()
            session.refresh(study_session)

            return {
                "ok": True,
                "study_session": (
                    study_session_to_dict(
                        study_session,
                        subject_name=subject.name,
                    )
                ),
            }

    @mcp.tool()
    def list_study_sessions(
        subject_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        activity_type: str | None = None,
        maximum_results: int = 100,
    ) -> dict:
        """Lista sesiones reales de estudio."""

        if maximum_results < 1 or maximum_results > 500:
            return {
                "ok": False,
                "error": (
                    "maximum_results debe estar "
                    "entre 1 y 500"
                ),
            }

        try:
            parsed_date_from = (
                date.fromisoformat(
                    date_from.strip()
                )
                if date_from
                and date_from.strip()
                else None
            )

            parsed_date_to = (
                date.fromisoformat(
                    date_to.strip()
                )
                if date_to
                and date_to.strip()
                else None
            )

        except ValueError:
            return {
                "ok": False,
                "error": (
                    "Las fechas deben usar YYYY-MM-DD"
                ),
            }

        clean_activity_type = (
            activity_type.strip().casefold()
            if activity_type
            and activity_type.strip()
            else None
        )

        with SessionLocal() as session:
            statement = select(
                StudySession
            )

            if subject_id is not None:
                statement = statement.where(
                    StudySession.subject_id
                    == subject_id
                )

            if parsed_date_from is not None:
                statement = statement.where(
                    StudySession.session_date
                    >= parsed_date_from
                )

            if parsed_date_to is not None:
                statement = statement.where(
                    StudySession.session_date
                    <= parsed_date_to
                )

            if clean_activity_type is not None:
                statement = statement.where(
                    StudySession.activity_type
                    == clean_activity_type
                )

            statement = statement.order_by(
                StudySession.session_date.desc(),
                StudySession.id.desc(),
            ).limit(maximum_results)

            study_sessions = session.scalars(
                statement
            ).all()

            results = []

            for study_session in study_sessions:
                subject = session.get(
                    Subject,
                    study_session.subject_id,
                )

                results.append(
                    study_session_to_dict(
                        study_session,
                        subject_name=(
                            subject.name
                            if subject
                            else None
                        ),
                    )
                )

            return {
                "ok": True,
                "result_count": len(results),
                "study_sessions": results,
            }

    @mcp.tool()
    def get_study_statistics(
        subject_id: int | None = None,
        days: int = 30,
    ) -> dict:
        """
        Calcula estadísticas, actividad semanal y rachas.

        days determina el periodo analizado.
        """

        if days < 1 or days > 3650:
            return {
                "ok": False,
                "error": (
                    "days debe estar entre 1 y 3650"
                ),
            }

        today = date.today()
        date_from = (
            today - timedelta(days=days - 1)
        )

        with SessionLocal() as session:
            statement = select(
                StudySession
            ).where(
                StudySession.session_date
                >= date_from,
                StudySession.session_date
                <= today,
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

                statement = statement.where(
                    StudySession.subject_id
                    == subject_id
                )
            else:
                subject = None

            study_sessions = session.scalars(
                statement.order_by(
                    StudySession.session_date.asc(),
                    StudySession.id.asc(),
                )
            ).all()

            total_minutes = sum(
                item.duration_minutes
                for item in study_sessions
            )

            active_dates = [
                item.session_date
                for item in study_sessions
            ]

            activity_minutes: dict[str, int] = (
                defaultdict(int)
            )

            subject_minutes: dict[int, int] = (
                defaultdict(int)
            )

            subject_names: dict[int, str] = {}

            daily_minutes: dict[str, int] = (
                defaultdict(int)
            )

            completed_plan_count = 0
            sessions_with_plan = 0

            focus_values = []
            difficulty_values = []
            satisfaction_values = []

            for item in study_sessions:
                activity_minutes[
                    item.activity_type
                ] += item.duration_minutes

                subject_minutes[
                    item.subject_id
                ] += item.duration_minutes

                daily_minutes[
                    item.session_date.isoformat()
                ] += item.duration_minutes

                if item.planned_minutes is not None:
                    sessions_with_plan += 1

                    if item.completed_plan:
                        completed_plan_count += 1

                if item.focus_rating is not None:
                    focus_values.append(
                        item.focus_rating
                    )

                if (
                    item.difficulty_rating
                    is not None
                ):
                    difficulty_values.append(
                        item.difficulty_rating
                    )

                if (
                    item.satisfaction_rating
                    is not None
                ):
                    satisfaction_values.append(
                        item.satisfaction_rating
                    )

            for subject_key in subject_minutes:
                subject_record = session.get(
                    Subject,
                    subject_key,
                )

                subject_names[subject_key] = (
                    subject_record.name
                    if subject_record
                    else f"Asignatura {subject_key}"
                )

            streaks = calculate_streaks(
                active_dates=active_dates,
                today=today,
            )

            average_session_minutes = (
                round(
                    total_minutes
                    / len(study_sessions),
                    2,
                )
                if study_sessions
                else 0
            )

            plan_completion_percentage = (
                round(
                    completed_plan_count
                    / sessions_with_plan
                    * 100,
                    2,
                )
                if sessions_with_plan > 0
                else None
            )

            def average_or_none(
                values: list[int],
            ) -> float | None:
                if not values:
                    return None

                return round(
                    sum(values) / len(values),
                    2,
                )

            return {
                "ok": True,
                "period": {
                    "days": days,
                    "date_from": (
                        date_from.isoformat()
                    ),
                    "date_to": today.isoformat(),
                },
                "subject": (
                    {
                        "id": subject.id,
                        "name": subject.name,
                    }
                    if subject is not None
                    else None
                ),
                "summary": {
                    "study_session_count": len(
                        study_sessions
                    ),
                    "total_minutes": total_minutes,
                    "total_hours": round(
                        total_minutes / 60,
                        2,
                    ),
                    "active_day_count": len(
                        set(active_dates)
                    ),
                    "average_session_minutes": (
                        average_session_minutes
                    ),
                    "current_streak_days": (
                        streaks[
                            "current_streak_days"
                        ]
                    ),
                    "longest_streak_days": (
                        streaks[
                            "longest_streak_days"
                        ]
                    ),
                    "sessions_with_plan": (
                        sessions_with_plan
                    ),
                    "completed_plan_count": (
                        completed_plan_count
                    ),
                    "plan_completion_percentage": (
                        plan_completion_percentage
                    ),
                    "average_focus_rating": (
                        average_or_none(
                            focus_values
                        )
                    ),
                    "average_difficulty_rating": (
                        average_or_none(
                            difficulty_values
                        )
                    ),
                    "average_satisfaction_rating": (
                        average_or_none(
                            satisfaction_values
                        )
                    ),
                },
                "minutes_by_activity": dict(
                    sorted(
                        activity_minutes.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                ),
                "minutes_by_subject": [
                    {
                        "subject_id": (
                            subject_key
                        ),
                        "subject_name": (
                            subject_names[
                                subject_key
                            ]
                        ),
                        "minutes": minutes,
                        "hours": round(
                            minutes / 60,
                            2,
                        ),
                    }
                    for subject_key, minutes
                    in sorted(
                        subject_minutes.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )
                ],
                "daily_activity": [
                    {
                        "date": day,
                        "minutes": minutes,
                    }
                    for day, minutes in sorted(
                        daily_minutes.items()
                    )
                ],
                "provider_called": False,
                "estimated_cost_usd": 0,
            }