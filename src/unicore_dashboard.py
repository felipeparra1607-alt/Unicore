import json
from datetime import date, datetime, timedelta

from sqlalchemy import select

from src.academic_risk_tools import (
    build_subject_risk,
)
from src.analytics_tools import (
    build_learning_analytics,
)
from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    AchievementUnlock,
    Assessment,
    BossBattle,
    DailyMission,
    GamificationEvent,
    GradeGoal,
    ReviewItem,
    StudyAttempt,
    StudySession,
    Subject,
)
from src.gamification_tools import (
    calculate_level,
    calculate_streak,
)


def safe_json_list(
    value: str | None,
) -> list:
    if not value:
        return []

    try:
        result = json.loads(value)

        if isinstance(result, list):
            return result

    except json.JSONDecodeError:
        pass

    return []


def calculate_grade_snapshot(
    assessments: list[Assessment],
    goal: GradeGoal | None,
) -> dict:
    active = [
        item
        for item in assessments
        if item.status != "cancelled"
    ]

    completed = [
        item
        for item in active
        if (
            item.status == "completed"
            and item.obtained_grade is not None
        )
    ]

    total_weight = sum(
        item.weight_percentage
        for item in active
    )

    evaluated_weight = sum(
        item.weight_percentage
        for item in completed
    )

    accumulated_percentage = sum(
        (
            item.obtained_grade
            / item.maximum_grade
        )
        * item.weight_percentage
        for item in completed
    )

    current_grade = (
        accumulated_percentage
        / evaluated_weight
        * 10
        if evaluated_weight > 0
        else None
    )

    target_grade = (
        goal.target_grade
        if goal
        else None
    )

    required_average = None

    if goal and evaluated_weight < 100:
        target_percentage = (
            goal.target_grade
            / goal.maximum_grade
            * 100
        )

        required_percentage = (
            target_percentage
            - accumulated_percentage
        )

        remaining_weight = (
            100 - evaluated_weight
        )

        if required_percentage <= 0:
            required_average = 0.0

        elif remaining_weight > 0:
            required_average = (
                required_percentage
                / remaining_weight
                * goal.maximum_grade
            )

    return {
        "current_grade_out_of_10": (
            round(current_grade, 2)
            if current_grade is not None
            else None
        ),
        "evaluated_weight_percentage": round(
            evaluated_weight,
            2,
        ),
        "defined_weight_percentage": round(
            total_weight,
            2,
        ),
        "accumulated_final_percentage": round(
            accumulated_percentage,
            2,
        ),
        "target_grade": target_grade,
        "required_average_on_remaining": (
            round(required_average, 2)
            if required_average is not None
            else None
        ),
    }


def build_dashboard_data(
    subject_id: int | None = None,
) -> dict:
    """
    Construye el estado completo del dashboard.

    No llama a ningún proveedor de IA.
    """

    today = date.today()
    week_start = today - timedelta(days=6)

    with SessionLocal() as session:
        selected_subject = None

        if subject_id is not None:
            selected_subject = session.get(
                Subject,
                subject_id,
            )

            if selected_subject is None:
                return {
                    "ok": False,
                    "error": (
                        "La asignatura no existe"
                    ),
                }

        subjects = session.scalars(
            select(Subject).order_by(
                Subject.name.asc()
            )
        ).all()

        study_statement = select(
            StudySession
        )

        attempt_statement = select(
            StudyAttempt
        ).where(
            StudyAttempt.status
            == "completed"
        )

        task_statement = select(
            AcademicTask
        ).where(
            AcademicTask.status.notin_(
                ["completed", "cancelled"]
            )
        )

        review_statement = select(
            ReviewItem
        )

        event_statement = select(
            GamificationEvent
        )

        mission_statement = select(
            DailyMission
        ).where(
            DailyMission.mission_date
            == today
        )

        boss_statement = select(
            BossBattle
        )

        achievement_statement = select(
            AchievementUnlock
        )

        assessment_statement = select(
            Assessment
        )

        if subject_id is not None:
            study_statement = (
                study_statement.where(
                    StudySession.subject_id
                    == subject_id
                )
            )

            attempt_statement = (
                attempt_statement.where(
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

            review_statement = (
                review_statement.where(
                    ReviewItem.subject_id
                    == subject_id
                )
            )

            event_statement = (
                event_statement.where(
                    GamificationEvent.subject_id
                    == subject_id
                )
            )

            mission_statement = (
                mission_statement.where(
                    DailyMission.subject_id
                    == subject_id
                )
            )

            boss_statement = (
                boss_statement.where(
                    BossBattle.subject_id
                    == subject_id
                )
            )

            achievement_statement = (
                achievement_statement.where(
                    AchievementUnlock.subject_id
                    == subject_id
                )
            )

            assessment_statement = (
                assessment_statement.where(
                    Assessment.subject_id
                    == subject_id
                )
            )

        study_sessions = session.scalars(
            study_statement
        ).all()

        attempts = session.scalars(
            attempt_statement
        ).all()

        pending_tasks = session.scalars(
            task_statement
        ).all()

        review_items = session.scalars(
            review_statement
        ).all()

        xp_events = session.scalars(
            event_statement
        ).all()

        missions = session.scalars(
            mission_statement.order_by(
                DailyMission.status.asc(),
                DailyMission.reward_xp.desc(),
            )
        ).all()

        bosses = session.scalars(
            boss_statement
        ).all()

        achievements = session.scalars(
            achievement_statement.order_by(
                AchievementUnlock.unlocked_at.desc()
            )
        ).all()

        assessments = session.scalars(
            assessment_statement
        ).all()

        total_xp = sum(
            item.xp_points
            for item in xp_events
        )

        level = calculate_level(
            total_xp
        )

        streak = calculate_streak(
            [
                item.session_date
                for item in study_sessions
            ]
        )

        study_minutes_week = sum(
            item.duration_minutes
            for item in study_sessions
            if (
                week_start
                <= item.session_date
                <= today
            )
        )

        study_minutes_today = sum(
            item.duration_minutes
            for item in study_sessions
            if item.session_date == today
        )

        quiz_scores = [
            item.score_percentage
            for item in attempts
            if item.score_percentage
            is not None
        ]

        quiz_average = (
            sum(quiz_scores)
            / len(quiz_scores)
            if quiz_scores
            else None
        )

        due_reviews = [
            item
            for item in review_items
            if (
                item.status != "mastered"
                and item.next_review_at
                <= datetime.utcnow()
            )
        ]

        overdue_tasks = [
            item
            for item in pending_tasks
            if (
                item.due_date is not None
                and item.due_date < today
            )
        ]

        urgent_tasks = sorted(
            pending_tasks,
            key=lambda item: (
                item.due_date is None,
                item.due_date or date.max,
                -item.priority,
            ),
        )

        daily_activity = []

        for day_offset in range(6, -1, -1):
            current_day = (
                today
                - timedelta(
                    days=day_offset
                )
            )

            minutes = sum(
                item.duration_minutes
                for item in study_sessions
                if (
                    item.session_date
                    == current_day
                )
            )

            daily_activity.append({
                "date": (
                    current_day.isoformat()
                ),
                "weekday": (
                    current_day.strftime(
                        "%a"
                    )
                ),
                "minutes": minutes,
            })

        upcoming_assessments = [
            item
            for item in assessments
            if (
                item.status == "pending"
                and item.assessment_date
                is not None
                and item.assessment_date
                >= today
            )
        ]

        upcoming_assessments.sort(
            key=lambda item: (
                item.assessment_date
            )
        )

        next_assessment = (
            upcoming_assessments[0]
            if upcoming_assessments
            else None
        )

        active_bosses = [
            item
            for item in bosses
            if item.status != "defeated"
        ]

        def boss_sort_key(
            boss: BossBattle,
        ):
            assessment = session.get(
                Assessment,
                boss.assessment_id,
            )

            return (
                assessment.assessment_date
                if (
                    assessment
                    and assessment.assessment_date
                )
                else date.max
            )

        active_bosses.sort(
            key=boss_sort_key
        )

        next_boss = None

        if active_bosses:
            boss = active_bosses[0]

            boss_assessment = session.get(
                Assessment,
                boss.assessment_id,
            )

            next_boss = {
                "id": boss.id,
                "title": boss.title,
                "assessment_title": (
                    boss_assessment.title
                    if boss_assessment
                    else None
                ),
                "assessment_date": (
                    boss_assessment.assessment_date
                    .isoformat()
                    if (
                        boss_assessment
                        and boss_assessment.assessment_date
                    )
                    else None
                ),
                "days_remaining": (
                    (
                        boss_assessment.assessment_date
                        - today
                    ).days
                    if (
                        boss_assessment
                        and boss_assessment.assessment_date
                    )
                    else None
                ),
                "readiness_percentage": (
                    boss.readiness_percentage
                ),
                "target_score_percentage": (
                    boss.target_score_percentage
                ),
                "reward_xp": boss.reward_xp,
                "weak_topics": safe_json_list(
                    boss.weak_topics_json
                ),
                "recommended_actions": (
                    safe_json_list(
                        boss.recommended_actions_json
                    )
                ),
            }

        goal_statement = select(
            GradeGoal
        )

        if subject_id is not None:
            goal_statement = (
                goal_statement.where(
                    GradeGoal.subject_id
                    == subject_id
                )
            )

        goals = session.scalars(
            goal_statement
        ).all()

        goals_by_subject = {
            item.subject_id: item
            for item in goals
        }

        if subject_id is not None:
            grade_snapshot = (
                calculate_grade_snapshot(
                    assessments,
                    goals_by_subject.get(
                        subject_id
                    ),
                )
            )
        else:
            grade_snapshot = None

        subject_cards = []

        for subject in subjects:
            subject_sessions = [
                item
                for item in study_sessions
                if item.subject_id
                == subject.id
            ]

            if (
                subject_id is not None
                and subject.id
                != subject_id
            ):
                continue

            subject_events = [
                item
                for item in xp_events
                if item.subject_id
                == subject.id
            ]

            subject_attempts = [
                item
                for item in attempts
                if item.subject_id
                == subject.id
            ]

            subject_tasks = [
                item
                for item in pending_tasks
                if item.subject_id
                == subject.id
            ]

            subject_assessments = [
                item
                for item in assessments
                if item.subject_id
                == subject.id
            ]

            subject_quiz_scores = [
                item.score_percentage
                for item in subject_attempts
                if item.score_percentage
                is not None
            ]

            subject_quiz_average = (
                sum(subject_quiz_scores)
                / len(subject_quiz_scores)
                if subject_quiz_scores
                else None
            )

            future_assessments = [
                item
                for item
                in subject_assessments
                if (
                    item.status == "pending"
                    and item.assessment_date
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

            subject_cards.append({
                "id": subject.id,
                "name": subject.name,
                "xp": sum(
                    item.xp_points
                    for item in subject_events
                ),
                "study_minutes": sum(
                    item.duration_minutes
                    for item in subject_sessions
                ),
                "quiz_average_percentage": (
                    round(
                        subject_quiz_average,
                        2,
                    )
                    if subject_quiz_average
                    is not None
                    else None
                ),
                "pending_task_count": len(
                    subject_tasks
                ),
                "next_assessment": (
                    {
                        "title": (
                            future_assessments[
                                0
                            ].title
                        ),
                        "date": (
                            future_assessments[
                                0
                            ].assessment_date
                            .isoformat()
                        ),
                    }
                    if future_assessments
                    else None
                ),
                "grade": (
                    calculate_grade_snapshot(
                        subject_assessments,
                        goals_by_subject.get(
                            subject.id
                        ),
                    )
                ),
            })

        mission_reward_total = sum(
            mission.reward_xp
            for mission in missions
        )

        mission_reward_earned = sum(
            mission.reward_xp
            for mission in missions
            if mission.status
            == "completed"
        )

        # Analítica avanzada:
        # compara las últimas dos ventanas de 14 días.
        analytics = (
            build_learning_analytics(
                subject_id=subject_id,
                comparison_days=14,
            )
        )

        # El riesgo solo tiene sentido en la vista
        # de una asignatura concreta.
        risk = None

        if subject_id is not None:
            risk_result = (
                build_subject_risk(
                    subject_id
                )
            )

            if risk_result.get("ok"):
                risk = risk_result

        return {
            "ok": True,
            "generated_at": (
                datetime.now().isoformat()
            ),
            "view": (
                "subject"
                if subject_id is not None
                else "global"
            ),
            "subject": (
                {
                    "id": (
                        selected_subject.id
                    ),
                    "name": (
                        selected_subject.name
                    ),
                }
                if selected_subject
                else None
            ),
            "hero": {
                **level,
                **streak,
            },
            "metrics": {
                "study_minutes_today": (
                    study_minutes_today
                ),
                "study_minutes_last_7_days": (
                    study_minutes_week
                ),
                "study_hours_last_7_days": round(
                    study_minutes_week / 60,
                    2,
                ),
                "study_session_count": len(
                    study_sessions
                ),
                "quiz_attempt_count": len(
                    attempts
                ),
                "quiz_average_percentage": (
                    round(
                        quiz_average,
                        2,
                    )
                    if quiz_average
                    is not None
                    else None
                ),
                "pending_task_count": len(
                    pending_tasks
                ),
                "overdue_task_count": len(
                    overdue_tasks
                ),
                "due_review_count": len(
                    due_reviews
                ),
                "achievement_count": len(
                    achievements
                ),
            },
            "daily_activity": (
                daily_activity
            ),
            "missions": {
                "total": len(missions),
                "completed": sum(
                    1
                    for mission in missions
                    if mission.status
                    == "completed"
                ),
                "reward_xp_available": (
                    mission_reward_total
                ),
                "reward_xp_earned": (
                    mission_reward_earned
                ),
                "items": [
                    {
                        "id": mission.id,
                        "title": mission.title,
                        "type": (
                            mission.mission_type
                        ),
                        "current_value": (
                            mission.current_value
                        ),
                        "target_value": (
                            mission.target_value
                        ),
                        "reward_xp": (
                            mission.reward_xp
                        ),
                        "status": (
                            mission.status
                        ),
                    }
                    for mission in missions
                ],
            },
            "next_boss": next_boss,
            "next_assessment": (
                {
                    "id": (
                        next_assessment.id
                    ),
                    "title": (
                        next_assessment.title
                    ),
                    "type": (
                        next_assessment
                        .assessment_type
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
                    "weight_percentage": (
                        next_assessment
                        .weight_percentage
                    ),
                }
                if next_assessment
                else None
            ),
            "grade": grade_snapshot,
            "priorities": [
                {
                    "id": task.id,
                    "title": task.title,
                    "subject_id": (
                        task.subject_id
                    ),
                    "priority": (
                        task.priority
                    ),
                    "status": (
                        task.status
                    ),
                    "due_date": (
                        task.due_date
                        .isoformat()
                        if task.due_date
                        else None
                    ),
                    "days_remaining": (
                        (
                            task.due_date
                            - today
                        ).days
                        if task.due_date
                        else None
                    ),
                    "progress_percentage": (
                        task.progress_percentage
                    ),
                }
                for task in urgent_tasks[:5]
            ],
            "achievements": [
                {
                    "title": item.title,
                    "description": (
                        item.description
                    ),
                    "unlocked_at": (
                        item.unlocked_at
                        .isoformat()
                    ),
                }
                for item in achievements[:5]
            ],
            "subjects": subject_cards,

            # Nuevas métricas avanzadas.
            "analytics": (
                analytics
                if analytics.get("ok")
                else None
            ),
            "academic_risk": risk,

            "provider_called": False,
            "estimated_cost_usd": 0,
        }


def register_unicore_dashboard_tools(
    mcp,
) -> None:
    """Registra el dashboard unificado."""

    @mcp.tool()
    def get_unicore_dashboard(
        subject_id: int | None = None,
    ) -> dict:
        """
        Devuelve todas las métricas importantes
        para el dashboard de UniCore.
        """

        return build_dashboard_data(
            subject_id=subject_id
        )