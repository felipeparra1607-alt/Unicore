from datetime import date, datetime, timedelta

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    AchievementUnlock,
    GamificationEvent,
    StudyAttempt,
    StudySession,
    Subject,
)


def xp_required_for_level(
    level: int,
) -> int:
    """
    XP total necesario para alcanzar un nivel.

    Nivel 1 = 0 XP
    Nivel 2 = 100 XP
    Nivel 3 = 250 XP
    Nivel 4 = 450 XP...
    """

    if level <= 1:
        return 0

    return int(
        50 * (level - 1) * level
    )


def calculate_level(
    total_xp: int,
) -> dict:
    """Calcula nivel y progreso hacia el siguiente."""

    level = 1

    while (
        xp_required_for_level(level + 1)
        <= total_xp
    ):
        level += 1

    current_level_start = (
        xp_required_for_level(level)
    )

    next_level_xp = (
        xp_required_for_level(level + 1)
    )

    xp_inside_level = (
        total_xp - current_level_start
    )

    level_span = (
        next_level_xp
        - current_level_start
    )

    progress_percentage = round(
        (
            xp_inside_level
            / level_span
            * 100
        )
        if level_span > 0
        else 100,
        2,
    )

    return {
        "level": level,
        "total_xp": total_xp,
        "current_level_start_xp": (
            current_level_start
        ),
        "next_level_xp": next_level_xp,
        "xp_until_next_level": max(
            0,
            next_level_xp - total_xp,
        ),
        "level_progress_percentage": (
            progress_percentage
        ),
    }


def calculate_streak(
    study_dates: list[date],
) -> dict:
    """Calcula racha actual y máxima."""

    unique_dates = sorted(
        set(study_dates)
    )

    if not unique_dates:
        return {
            "current_streak": 0,
            "longest_streak": 0,
        }

    longest = 1
    running = 1

    for previous, current in zip(
        unique_dates,
        unique_dates[1:],
    ):
        if (
            current - previous
            == timedelta(days=1)
        ):
            running += 1
            longest = max(
                longest,
                running,
            )
        else:
            running = 1

    today = date.today()
    active_dates = set(unique_dates)

    if today in active_dates:
        cursor = today
    elif (
        today - timedelta(days=1)
        in active_dates
    ):
        cursor = today - timedelta(days=1)
    else:
        return {
            "current_streak": 0,
            "longest_streak": longest,
        }

    current_streak = 0

    while cursor in active_dates:
        current_streak += 1
        cursor -= timedelta(days=1)

    return {
        "current_streak": current_streak,
        "longest_streak": longest,
    }


def create_xp_event_if_missing(
    session,
    *,
    source_key: str,
    event_type: str,
    xp_points: int,
    description: str,
    subject_id: int | None = None,
) -> bool:
    """Crea un evento solo si todavía no existe."""

    existing = session.scalar(
        select(GamificationEvent).where(
            GamificationEvent.source_key
            == source_key
        )
    )

    if existing is not None:
        return False

    session.add(
        GamificationEvent(
            subject_id=subject_id,
            event_type=event_type,
            source_key=source_key,
            xp_points=xp_points,
            description=description,
        )
    )

    return True


def unlock_achievement_if_missing(
    session,
    *,
    achievement_key: str,
    title: str,
    description: str,
    subject_id: int | None = None,
) -> bool:
    """Desbloquea un logro una sola vez."""

    statement = select(
        AchievementUnlock
    ).where(
        AchievementUnlock.achievement_key
        == achievement_key
    )

    if subject_id is None:
        statement = statement.where(
            AchievementUnlock.subject_id
            .is_(None)
        )
    else:
        statement = statement.where(
            AchievementUnlock.subject_id
            == subject_id
        )

    existing = session.scalar(
        statement
    )

    if existing is not None:
        return False

    session.add(
        AchievementUnlock(
            achievement_key=achievement_key,
            subject_id=subject_id,
            title=title,
            description=description,
        )
    )

    return True


def register_gamification_tools(mcp) -> None:
    """Registra XP, niveles, rachas y logros."""

    @mcp.tool()
    def sync_gamification(
        subject_id: int | None = None,
    ) -> dict:
        """
        Convierte actividad académica existente
        en XP sin duplicar recompensas.
        """

        created_events = 0
        new_achievements = []

        with SessionLocal() as session:
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
            )

            quiz_statement = select(
                StudyAttempt
            ).where(
                StudyAttempt.status
                == "completed"
            )

            task_statement = select(
                AcademicTask
            ).where(
                AcademicTask.status
                == "completed"
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

            completed_quizzes = session.scalars(
                quiz_statement
            ).all()

            completed_tasks = session.scalars(
                task_statement
            ).all()

            for item in study_sessions:
                xp = min(
                    item.duration_minutes,
                    120,
                )

                created = (
                    create_xp_event_if_missing(
                        session,
                        source_key=(
                            f"study_session:{item.id}"
                        ),
                        event_type="study_session",
                        xp_points=xp,
                        description=(
                            f"{item.duration_minutes} "
                            "minutos de estudio"
                        ),
                        subject_id=item.subject_id,
                    )
                )

                if created:
                    created_events += 1

            for attempt in completed_quizzes:
                score = (
                    attempt.score_percentage
                    or 0
                )

                bonus = int(
                    score // 10
                )

                xp = 20 + bonus

                created = (
                    create_xp_event_if_missing(
                        session,
                        source_key=(
                            f"quiz_attempt:"
                            f"{attempt.id}"
                        ),
                        event_type="quiz_completed",
                        xp_points=xp,
                        description=(
                            "Quiz completado con "
                            f"{round(score, 2)} %"
                        ),
                        subject_id=(
                            attempt.subject_id
                        ),
                    )
                )

                if created:
                    created_events += 1

            for task in completed_tasks:
                xp = 30 + (
                    task.priority * 5
                )

                created = (
                    create_xp_event_if_missing(
                        session,
                        source_key=(
                            f"academic_task:"
                            f"{task.id}"
                        ),
                        event_type="task_completed",
                        xp_points=xp,
                        description=(
                            "Tarea completada: "
                            f"{task.title}"
                        ),
                        subject_id=(
                            task.subject_id
                        ),
                    )
                )

                if created:
                    created_events += 1

            session.flush()

            xp_statement = select(
                GamificationEvent
            )

            all_study_statement = select(
                StudySession
            )

            if subject_id is not None:
                xp_statement = (
                    xp_statement.where(
                        GamificationEvent.subject_id
                        == subject_id
                    )
                )

                all_study_statement = (
                    all_study_statement.where(
                        StudySession.subject_id
                        == subject_id
                    )
                )

            xp_events = session.scalars(
                xp_statement
            ).all()

            streak_sessions = session.scalars(
                all_study_statement
            ).all()

            total_xp = sum(
                event.xp_points
                for event in xp_events
            )

            streak = calculate_streak(
                [
                    item.session_date
                    for item in streak_sessions
                ]
            )

            achievements_to_check = [
                (
                    "first_100_xp",
                    total_xp >= 100,
                    "Primer centenar",
                    "Has conseguido 100 XP.",
                ),
                (
                    "first_500_xp",
                    total_xp >= 500,
                    "En marcha",
                    "Has conseguido 500 XP.",
                ),
                (
                    "streak_3",
                    streak["longest_streak"] >= 3,
                    "Tres días seguidos",
                    (
                        "Has estudiado durante "
                        "3 días consecutivos."
                    ),
                ),
                (
                    "streak_7",
                    streak["longest_streak"] >= 7,
                    "Semana perfecta",
                    (
                        "Has estudiado durante "
                        "7 días consecutivos."
                    ),
                ),
                (
                    "five_study_sessions",
                    len(streak_sessions) >= 5,
                    "Constancia",
                    (
                        "Has registrado "
                        "5 sesiones de estudio."
                    ),
                ),
                (
                    "ten_study_sessions",
                    len(streak_sessions) >= 10,
                    "En serio",
                    (
                        "Has registrado "
                        "10 sesiones de estudio."
                    ),
                ),
            ]

            for (
                key,
                condition,
                title,
                description,
            ) in achievements_to_check:

                if not condition:
                    continue

                unlocked = (
                    unlock_achievement_if_missing(
                        session,
                        achievement_key=key,
                        title=title,
                        description=description,
                        subject_id=subject_id,
                    )
                )

                if unlocked:
                    new_achievements.append(
                        title
                    )

            # Logro por quiz >= 90 %
            if any(
                (
                    attempt.score_percentage
                    or 0
                )
                >= 90
                for attempt
                in completed_quizzes
            ):
                unlocked = (
                    unlock_achievement_if_missing(
                        session,
                        achievement_key=(
                            "quiz_90"
                        ),
                        title="Dominio demostrado",
                        description=(
                            "Has conseguido al menos "
                            "90 % en un quiz."
                        ),
                        subject_id=subject_id,
                    )
                )

                if unlocked:
                    new_achievements.append(
                        "Dominio demostrado"
                    )

            session.commit()

            level_data = calculate_level(
                total_xp
            )

            return {
                "ok": True,
                "new_xp_events": (
                    created_events
                ),
                "new_achievements": (
                    new_achievements
                ),
                "gamification": {
                    **level_data,
                    **streak,
                },
                "provider_called": False,
                "estimated_cost_usd": 0,
            }

    @mcp.tool()
    def get_gamification_profile(
        subject_id: int | None = None,
    ) -> dict:
        """Devuelve el perfil de progreso gamificado."""

        with SessionLocal() as session:
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
            else:
                subject = None

            event_statement = select(
                GamificationEvent
            )

            study_statement = select(
                StudySession
            )

            achievement_statement = select(
                AchievementUnlock
            )

            if subject_id is not None:
                event_statement = (
                    event_statement.where(
                        GamificationEvent.subject_id
                        == subject_id
                    )
                )

                study_statement = (
                    study_statement.where(
                        StudySession.subject_id
                        == subject_id
                    )
                )

                achievement_statement = (
                    achievement_statement.where(
                        AchievementUnlock.subject_id
                        == subject_id
                    )
                )

            events = session.scalars(
                event_statement.order_by(
                    GamificationEvent.created_at.desc()
                )
            ).all()

            study_sessions = session.scalars(
                study_statement
            ).all()

            achievements = session.scalars(
                achievement_statement.order_by(
                    AchievementUnlock.unlocked_at.desc()
                )
            ).all()

            total_xp = sum(
                event.xp_points
                for event in events
            )

            streak = calculate_streak(
                [
                    item.session_date
                    for item in study_sessions
                ]
            )

            level_data = calculate_level(
                total_xp
            )

            xp_by_type = {}

            for event in events:
                xp_by_type[event.event_type] = (
                    xp_by_type.get(
                        event.event_type,
                        0,
                    )
                    + event.xp_points
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
                "profile": {
                    **level_data,
                    **streak,
                    "achievement_count": (
                        len(achievements)
                    ),
                },
                "xp_by_type": xp_by_type,
                "achievements": [
                    {
                        "key": (
                            item.achievement_key
                        ),
                        "title": item.title,
                        "description": (
                            item.description
                        ),
                        "unlocked_at": (
                            item.unlocked_at
                            .isoformat()
                        ),
                    }
                    for item in achievements
                ],
                "recent_xp_events": [
                    {
                        "event_type": (
                            item.event_type
                        ),
                        "xp_points": (
                            item.xp_points
                        ),
                        "description": (
                            item.description
                        ),
                        "created_at": (
                            item.created_at
                            .isoformat()
                        ),
                    }
                    for item in events[:10]
                ],
                "provider_called": False,
                "estimated_cost_usd": 0,
            }