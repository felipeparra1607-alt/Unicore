from datetime import date, datetime

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    DailyMission,
    GamificationEvent,
    ReviewItem,
    StudySession,
    Subject,
)


def mission_to_dict(
    mission: DailyMission,
) -> dict:
    return {
        "id": mission.id,
        "mission_date": (
            mission.mission_date.isoformat()
        ),
        "subject_id": mission.subject_id,
        "mission_type": mission.mission_type,
        "source_key": mission.source_key,
        "title": mission.title,
        "target_value": mission.target_value,
        "current_value": mission.current_value,
        "reward_xp": mission.reward_xp,
        "status": mission.status,
        "completed_at": (
            mission.completed_at.isoformat()
            if mission.completed_at
            else None
        ),
    }


def create_mission_if_missing(
    session,
    *,
    mission_date: date,
    subject_id: int | None,
    mission_type: str,
    source_key: str,
    title: str,
    target_value: int,
    reward_xp: int,
) -> bool:
    """Crea una misión solo una vez por fecha."""

    existing = session.scalar(
        select(DailyMission).where(
            DailyMission.mission_date
            == mission_date,
            DailyMission.source_key
            == source_key,
        )
    )

    if existing is not None:
        return False

    session.add(
        DailyMission(
            mission_date=mission_date,
            subject_id=subject_id,
            mission_type=mission_type,
            source_key=source_key,
            title=title,
            target_value=target_value,
            current_value=0,
            reward_xp=reward_xp,
            status="active",
            updated_at=datetime.utcnow(),
        )
    )

    return True


def register_mission_tools(mcp) -> None:
    """Registra misiones diarias locales."""

    @mcp.tool()
    def generate_daily_missions(
        subject_id: int | None = None,
        maximum_missions: int = 3,
    ) -> dict:
        """
        Genera las misiones del día según
        la situación académica real.
        """

        if (
            maximum_missions < 1
            or maximum_missions > 5
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_missions debe estar "
                    "entre 1 y 5"
                ),
            }

        today = date.today()
        created = 0

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

            review_statement = select(
                ReviewItem
            ).where(
                ReviewItem.next_review_at
                <= datetime.utcnow()
            )

            task_statement = select(
                AcademicTask
            ).where(
                AcademicTask.status.notin_(
                    ["completed", "cancelled"]
                )
            )

            if subject_id is not None:
                review_statement = (
                    review_statement.where(
                        ReviewItem.subject_id
                        == subject_id
                    )
                )

                task_statement = (
                    task_statement.where(
                        AcademicTask.subject_id
                        == subject_id
                    )
                )

            due_reviews = session.scalars(
                review_statement
            ).all()

            pending_tasks = session.scalars(
                task_statement.order_by(
                    AcademicTask.due_date.asc(),
                    AcademicTask.priority.desc(),
                )
            ).all()

            mission_candidates = []

            if due_reviews:
                target = min(
                    len(due_reviews),
                    3,
                )

                mission_candidates.append({
                    "mission_type": "review",
                    "source_key": (
                        f"review:{subject_id or 'all'}"
                    ),
                    "title": (
                        f"Completa {target} "
                        "repaso(s) pendiente(s)"
                    ),
                    "target_value": target,
                    "reward_xp": 20,
                })

            if pending_tasks:
                task = pending_tasks[0]

                mission_candidates.append({
                    "mission_type": "task_progress",
                    "source_key": (
                        f"task_progress:{task.id}"
                    ),
                    "title": (
                        "Avanza en: "
                        f"{task.title}"
                    ),
                    "target_value": 1,
                    "reward_xp": 25,
                })

            mission_candidates.append({
                "mission_type": "study_minutes",
                "source_key": (
                    f"study_minutes:"
                    f"{subject_id or 'all'}"
                ),
                "title": (
                    "Estudia al menos 30 minutos"
                ),
                "target_value": 30,
                "reward_xp": 20,
            })

            mission_candidates.append({
                "mission_type": "focus_session",
                "source_key": (
                    f"focus_session:"
                    f"{subject_id or 'all'}"
                ),
                "title": (
                    "Completa una sesión "
                    "de estudio concentrada"
                ),
                "target_value": 1,
                "reward_xp": 15,
            })

            for candidate in (
                mission_candidates[
                    :maximum_missions
                ]
            ):
                was_created = (
                    create_mission_if_missing(
                        session,
                        mission_date=today,
                        subject_id=subject_id,
                        **candidate,
                    )
                )

                if was_created:
                    created += 1

            session.commit()

            missions = session.scalars(
                select(DailyMission)
                .where(
                    DailyMission.mission_date
                    == today
                )
                .order_by(
                    DailyMission.id.asc()
                )
            ).all()

            if subject_id is not None:
                missions = [
                    item
                    for item in missions
                    if item.subject_id
                    == subject_id
                ]

            return {
                "ok": True,
                "mission_date": (
                    today.isoformat()
                ),
                "new_missions_created": created,
                "mission_count": len(
                    missions
                ),
                "missions": [
                    mission_to_dict(item)
                    for item in missions
                ],
                "provider_called": False,
                "estimated_cost_usd": 0,
            }

    @mcp.tool()
    def sync_daily_missions(
        subject_id: int | None = None,
    ) -> dict:
        """
        Actualiza automáticamente las misiones de hoy
        y concede su XP cuando se completan.

        El XP solo puede concederse una vez por misión.
        """

        today = date.today()
        now = datetime.utcnow()

        with SessionLocal() as session:
            statement = select(
                DailyMission
            ).where(
                DailyMission.mission_date
                == today
            )

            if subject_id is not None:
                statement = statement.where(
                    DailyMission.subject_id
                    == subject_id
                )

            missions = session.scalars(
                statement
            ).all()

            updated = 0
            newly_completed = 0
            rewarded_missions = 0
            xp_awarded = 0

            for mission in missions:
                was_completed_before = (
                    mission.status
                    == "completed"
                )

                if not was_completed_before:
                    previous_value = (
                        mission.current_value
                    )

                    if (
                        mission.mission_type
                        == "study_minutes"
                    ):
                        study_statement = select(
                            StudySession
                        ).where(
                            StudySession.session_date
                            == today
                        )

                        if mission.subject_id is not None:
                            study_statement = (
                                study_statement.where(
                                    StudySession.subject_id
                                    == mission.subject_id
                                )
                            )

                        sessions = session.scalars(
                            study_statement
                        ).all()

                        mission.current_value = sum(
                            item.duration_minutes
                            for item in sessions
                        )

                    elif (
                        mission.mission_type
                        == "focus_session"
                    ):
                        study_statement = select(
                            StudySession
                        ).where(
                            StudySession.session_date
                            == today,
                            StudySession.duration_minutes
                            >= 25,
                        )

                        if mission.subject_id is not None:
                            study_statement = (
                                study_statement.where(
                                    StudySession.subject_id
                                    == mission.subject_id
                                )
                            )

                        focused_sessions = (
                            session.scalars(
                                study_statement
                            ).all()
                        )

                        mission.current_value = min(
                            len(focused_sessions),
                            mission.target_value,
                        )

                    elif (
                        mission.mission_type
                        == "task_progress"
                    ):
                        task_id = int(
                            mission.source_key.split(
                                ":",
                                1,
                            )[1]
                        )

                        task = session.get(
                            AcademicTask,
                            task_id,
                        )

                        if task is not None:
                            mission.current_value = (
                                1
                                if (
                                    task.status
                                    == "completed"
                                    or task.progress_percentage
                                    > 0
                                )
                                else 0
                            )

                    elif (
                        mission.mission_type
                        == "review"
                    ):
                        review_statement = select(
                            ReviewItem
                        ).where(
                            ReviewItem.last_reviewed_at
                            .is_not(None)
                        )

                        if mission.subject_id is not None:
                            review_statement = (
                                review_statement.where(
                                    ReviewItem.subject_id
                                    == mission.subject_id
                                )
                            )

                        review_items = session.scalars(
                            review_statement
                        ).all()

                        reviewed_today = [
                            item
                            for item in review_items
                            if (
                                item.last_reviewed_at
                                and item.last_reviewed_at.date()
                                == today
                            )
                        ]

                        mission.current_value = min(
                            len(reviewed_today),
                            mission.target_value,
                        )

                    if (
                        mission.current_value
                        != previous_value
                    ):
                        updated += 1

                    if (
                        mission.current_value
                        >= mission.target_value
                    ):
                        mission.current_value = (
                            mission.target_value
                        )

                        mission.status = "completed"
                        mission.completed_at = now
                        newly_completed += 1

                    mission.updated_at = now

                if mission.status == "completed":
                    reward_source_key = (
                        f"daily_mission:{mission.id}"
                    )

                    existing_reward = session.scalar(
                        select(
                            GamificationEvent
                        ).where(
                            GamificationEvent.source_key
                            == reward_source_key
                        )
                    )

                    if existing_reward is None:
                        session.add(
                            GamificationEvent(
                                subject_id=(
                                    mission.subject_id
                                ),
                                event_type=(
                                    "daily_mission_completed"
                                ),
                                source_key=(
                                    reward_source_key
                                ),
                                xp_points=(
                                    mission.reward_xp
                                ),
                                description=(
                                    "Misión completada: "
                                    f"{mission.title}"
                                ),
                            )
                        )

                        rewarded_missions += 1
                        xp_awarded += (
                            mission.reward_xp
                        )

            session.commit()

            return {
                "ok": True,
                "mission_date": (
                    today.isoformat()
                ),
                "updated_mission_count": (
                    updated
                ),
                "newly_completed_count": (
                    newly_completed
                ),
                "rewarded_mission_count": (
                    rewarded_missions
                ),
                "xp_awarded": xp_awarded,
                "missions": [
                    mission_to_dict(item)
                    for item in missions
                ],
                "provider_called": False,
                "estimated_cost_usd": 0,
            }
    @mcp.tool()
    def get_daily_missions(
        subject_id: int | None = None,
    ) -> dict:
        """Muestra las misiones del día."""

        today = date.today()

        with SessionLocal() as session:
            statement = select(
                DailyMission
            ).where(
                DailyMission.mission_date
                == today
            )

            if subject_id is not None:
                statement = statement.where(
                    DailyMission.subject_id
                    == subject_id
                )

            missions = session.scalars(
                statement.order_by(
                    DailyMission.status.asc(),
                    DailyMission.id.asc(),
                )
            ).all()

            earned_reward_xp = sum(
                item.reward_xp
                for item in missions
                if item.status
                == "completed"
            )

            possible_reward_xp = sum(
                item.reward_xp
                for item in missions
            )

            return {
                "ok": True,
                "mission_date": (
                    today.isoformat()
                ),
                "mission_count": len(
                    missions
                ),
                "completed_count": sum(
                    1
                    for item in missions
                    if item.status
                    == "completed"
                ),
                "earned_reward_xp": (
                    earned_reward_xp
                ),
                "possible_reward_xp": (
                    possible_reward_xp
                ),
                "missions": [
                    mission_to_dict(item)
                    for item in missions
                ],
                "provider_called": False,
                "estimated_cost_usd": 0,
            }