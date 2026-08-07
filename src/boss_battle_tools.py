import json
from datetime import date, datetime

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    Assessment,
    BossBattle,
    GamificationEvent,
    ReviewItem,
    StudyAttempt,
    StudySession,
    Subject,
)


def json_load_list(
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


def boss_to_dict(
    boss: BossBattle,
    assessment: Assessment,
    subject: Subject,
) -> dict:
    today = date.today()

    days_until_battle = (
        (
            assessment.assessment_date
            - today
        ).days
        if assessment.assessment_date
        else None
    )

    return {
        "id": boss.id,
        "subject_id": boss.subject_id,
        "subject_name": subject.name,
        "assessment_id": (
            boss.assessment_id
        ),
        "assessment_title": (
            assessment.title
        ),
        "assessment_date": (
            assessment.assessment_date
            .isoformat()
            if assessment.assessment_date
            else None
        ),
        "days_until_battle": (
            days_until_battle
        ),
        "title": boss.title,
        "status": boss.status,
        "target_score_percentage": (
            boss.target_score_percentage
        ),
        "readiness_percentage": (
            boss.readiness_percentage
        ),
        "weak_topics": json_load_list(
            boss.weak_topics_json
        ),
        "recommended_actions": (
            json_load_list(
                boss.recommended_actions_json
            )
        ),
        "reward_xp": boss.reward_xp,
        "best_score_percentage": (
            boss.best_score_percentage
        ),
        "attempt_count": (
            boss.attempt_count
        ),
        "defeated_at": (
            boss.defeated_at.isoformat()
            if boss.defeated_at
            else None
        ),
    }


def collect_weak_topics(
    attempts: list[StudyAttempt],
) -> list[dict]:
    """Extrae temas débiles de quizzes anteriores."""

    weak_topics = {}

    for attempt in attempts:
        if not attempt.results_json:
            continue

        try:
            results = json.loads(
                attempt.results_json
            )
        except json.JSONDecodeError:
            continue

        if not isinstance(results, dict):
            continue

        answers = results.get(
            "answers",
            [],
        )

        if not isinstance(answers, list):
            continue

        for answer in answers:
            if not isinstance(answer, dict):
                continue

            if answer.get("is_correct"):
                continue

            topic = (
                answer.get("topic")
                or attempt.topic
                or "Tema sin especificar"
            )

            if topic not in weak_topics:
                weak_topics[topic] = 0

            weak_topics[topic] += 1

    return [
        {
            "topic": topic,
            "incorrect_answer_count": count,
        }
        for topic, count in sorted(
            weak_topics.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


def calculate_readiness(
    *,
    quiz_average: float | None,
    due_review_count: int,
    study_minutes_last_14_days: int,
    days_until_exam: int | None,
) -> float:
    """
    Calcula una estimación simple de preparación.

    No representa una probabilidad real de aprobar.
    Es una métrica interna de progreso.
    """

    score = 0.0

    if quiz_average is not None:
        score += (
            min(
                quiz_average,
                100,
            )
            * 0.60
        )

    study_component = min(
        study_minutes_last_14_days / 300,
        1,
    )

    score += (
        study_component
        * 25
    )

    review_component = max(
        0,
        15 - min(
            due_review_count * 3,
            15,
        ),
    )

    score += review_component

    if (
        days_until_exam is not None
        and days_until_exam < 0
    ):
        return 0.0

    return round(
        min(score, 100),
        2,
    )


def register_boss_battle_tools(mcp) -> None:
    """Registra Boss Battles académicos."""

    @mcp.tool()
    def create_boss_battle(
        assessment_id: int,
        target_score_percentage: float = 80.0,
        reward_xp: int = 150,
    ) -> dict:
        """
        Convierte un examen pendiente
        en un Boss Battle.
        """

        if (
            target_score_percentage < 1
            or target_score_percentage > 100
        ):
            return {
                "ok": False,
                "error": (
                    "target_score_percentage debe "
                    "estar entre 1 y 100"
                ),
            }

        if reward_xp < 1 or reward_xp > 10000:
            return {
                "ok": False,
                "error": (
                    "reward_xp debe estar "
                    "entre 1 y 10000"
                ),
            }

        with SessionLocal() as session:
            assessment = session.get(
                Assessment,
                assessment_id,
            )

            if assessment is None:
                return {
                    "ok": False,
                    "error": (
                        "La evaluación no existe"
                    ),
                }

            if assessment.assessment_type != "exam":
                return {
                    "ok": False,
                    "error": (
                        "Los Boss Battles se crean "
                        "sobre evaluaciones de tipo exam"
                    ),
                }

            subject = session.get(
                Subject,
                assessment.subject_id,
            )

            existing = session.scalar(
                select(BossBattle).where(
                    BossBattle.assessment_id
                    == assessment_id
                )
            )

            if existing is not None:
                return {
                    "ok": True,
                    "created": False,
                    "boss_battle": boss_to_dict(
                        existing,
                        assessment,
                        subject,
                    ),
                }

            boss = BossBattle(
                subject_id=(
                    assessment.subject_id
                ),
                assessment_id=assessment.id,
                title=(
                    "Boss Battle: "
                    f"{assessment.title}"
                ),
                status="preparing",
                target_score_percentage=(
                    target_score_percentage
                ),
                readiness_percentage=0,
                weak_topics_json="[]",
                recommended_actions_json="[]",
                reward_xp=reward_xp,
                attempt_count=0,
                updated_at=datetime.utcnow(),
            )

            session.add(boss)
            session.commit()
            session.refresh(boss)

            return {
                "ok": True,
                "created": True,
                "boss_battle": boss_to_dict(
                    boss,
                    assessment,
                    subject,
                ),
                "provider_called": False,
                "estimated_cost_usd": 0,
            }

    @mcp.tool()
    def sync_boss_battle(
        boss_battle_id: int,
    ) -> dict:
        """
        Actualiza debilidades, preparación y
        recomendaciones del Boss Battle.
        """

        today = date.today()

        with SessionLocal() as session:
            boss = session.get(
                BossBattle,
                boss_battle_id,
            )

            if boss is None:
                return {
                    "ok": False,
                    "error": (
                        "El Boss Battle no existe"
                    ),
                }

            assessment = session.get(
                Assessment,
                boss.assessment_id,
            )

            subject = session.get(
                Subject,
                boss.subject_id,
            )

            attempts = session.scalars(
                select(StudyAttempt).where(
                    StudyAttempt.subject_id
                    == boss.subject_id,
                    StudyAttempt.status
                    == "completed",
                )
            ).all()

            scored_attempts = [
                item
                for item in attempts
                if item.score_percentage
                is not None
            ]

            quiz_average = (
                sum(
                    item.score_percentage
                    for item in scored_attempts
                )
                / len(scored_attempts)
                if scored_attempts
                else None
            )

            weak_topics = collect_weak_topics(
                attempts
            )

            due_reviews = session.scalars(
                select(ReviewItem).where(
                    ReviewItem.subject_id
                    == boss.subject_id,
                    ReviewItem.next_review_at
                    <= datetime.utcnow(),
                    ReviewItem.status
                    != "mastered",
                )
            ).all()

            study_sessions = session.scalars(
                select(StudySession).where(
                    StudySession.subject_id
                    == boss.subject_id
                )
            ).all()

            recent_study_minutes = sum(
                item.duration_minutes
                for item in study_sessions
                if (
                    today - item.session_date
                ).days
                <= 13
                and (
                    today - item.session_date
                ).days
                >= 0
            )

            days_until_exam = (
                (
                    assessment.assessment_date
                    - today
                ).days
                if assessment.assessment_date
                else None
            )

            readiness = calculate_readiness(
                quiz_average=quiz_average,
                due_review_count=len(
                    due_reviews
                ),
                study_minutes_last_14_days=(
                    recent_study_minutes
                ),
                days_until_exam=(
                    days_until_exam
                ),
            )

            recommendations = []

            if due_reviews:
                recommendations.append({
                    "priority": 1,
                    "action": (
                        "Completar repasos pendientes"
                    ),
                    "reason": (
                        f"Hay {len(due_reviews)} "
                        "repaso(s) vencido(s)."
                    ),
                })

            if weak_topics:
                recommendations.append({
                    "priority": 2,
                    "action": (
                        "Practicar los temas "
                        "con más errores"
                    ),
                    "topics": (
                        weak_topics[:5]
                    ),
                })

            if (
                quiz_average is None
                or quiz_average
                < boss.target_score_percentage
            ):
                recommendations.append({
                    "priority": 3,
                    "action": (
                        "Realizar un quiz "
                        "de preparación"
                    ),
                    "reason": (
                        "La media actual de quizzes "
                        "todavía no alcanza el objetivo."
                    ),
                })

            if recent_study_minutes < 120:
                recommendations.append({
                    "priority": 4,
                    "action": (
                        "Aumentar tiempo reciente "
                        "de preparación"
                    ),
                    "reason": (
                        "Hay menos de 120 minutos "
                        "registrados en los últimos "
                        "14 días."
                    ),
                })

            boss.readiness_percentage = (
                readiness
            )

            boss.weak_topics_json = (
                json.dumps(
                    weak_topics,
                    ensure_ascii=False,
                )
            )

            boss.recommended_actions_json = (
                json.dumps(
                    recommendations,
                    ensure_ascii=False,
                )
            )

            boss.updated_at = (
                datetime.utcnow()
            )

            session.commit()
            session.refresh(boss)

            return {
                "ok": True,
                "boss_battle": boss_to_dict(
                    boss,
                    assessment,
                    subject,
                ),
                "metrics": {
                    "quiz_attempt_count": len(
                        scored_attempts
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
                    "due_review_count": len(
                        due_reviews
                    ),
                    "study_minutes_last_14_days": (
                        recent_study_minutes
                    ),
                },
                "readiness_note": (
                    "readiness_percentage es una "
                    "métrica interna de progreso, "
                    "no una predicción de la nota."
                ),
                "provider_called": False,
                "estimated_cost_usd": 0,
            }

    @mcp.tool()
    def submit_boss_battle_result(
        boss_battle_id: int,
        score_percentage: float,
    ) -> dict:
        """
        Registra un intento de Boss Battle.

        Si alcanza el objetivo, derrota al Boss
        y concede XP una sola vez.
        """

        if (
            score_percentage < 0
            or score_percentage > 100
        ):
            return {
                "ok": False,
                "error": (
                    "score_percentage debe estar "
                    "entre 0 y 100"
                ),
            }

        with SessionLocal() as session:
            boss = session.get(
                BossBattle,
                boss_battle_id,
            )

            if boss is None:
                return {
                    "ok": False,
                    "error": (
                        "El Boss Battle no existe"
                    ),
                }

            assessment = session.get(
                Assessment,
                boss.assessment_id,
            )

            subject = session.get(
                Subject,
                boss.subject_id,
            )

            boss.attempt_count += 1

            if (
                boss.best_score_percentage is None
                or score_percentage
                > boss.best_score_percentage
            ):
                boss.best_score_percentage = (
                    score_percentage
                )

            defeated_now = False
            xp_awarded = 0

            if (
                score_percentage
                >= boss.target_score_percentage
            ):
                if boss.status != "defeated":
                    boss.status = "defeated"
                    boss.defeated_at = (
                        datetime.utcnow()
                    )

                    defeated_now = True

                source_key = (
                    f"boss_battle:{boss.id}"
                )

                existing_reward = session.scalar(
                    select(
                        GamificationEvent
                    ).where(
                        GamificationEvent.source_key
                        == source_key
                    )
                )

                if existing_reward is None:
                    session.add(
                        GamificationEvent(
                            subject_id=(
                                boss.subject_id
                            ),
                            event_type=(
                                "boss_battle_defeated"
                            ),
                            source_key=source_key,
                            xp_points=(
                                boss.reward_xp
                            ),
                            description=(
                                "Boss derrotado: "
                                f"{boss.title}"
                            ),
                        )
                    )

                    xp_awarded = (
                        boss.reward_xp
                    )

            boss.updated_at = (
                datetime.utcnow()
            )

            session.commit()
            session.refresh(boss)

            return {
                "ok": True,
                "defeated_now": (
                    defeated_now
                ),
                "xp_awarded": xp_awarded,
                "boss_battle": boss_to_dict(
                    boss,
                    assessment,
                    subject,
                ),
                "provider_called": False,
                "estimated_cost_usd": 0,
            }

    @mcp.tool()
    def list_boss_battles(
        subject_id: int | None = None,
    ) -> dict:
        """Lista los Boss Battles."""

        with SessionLocal() as session:
            statement = select(
                BossBattle
            )

            if subject_id is not None:
                statement = statement.where(
                    BossBattle.subject_id
                    == subject_id
                )

            bosses = session.scalars(
                statement.order_by(
                    BossBattle.status.asc(),
                    BossBattle.id.asc(),
                )
            ).all()

            results = []

            for boss in bosses:
                assessment = session.get(
                    Assessment,
                    boss.assessment_id,
                )

                subject = session.get(
                    Subject,
                    boss.subject_id,
                )

                results.append(
                    boss_to_dict(
                        boss,
                        assessment,
                        subject,
                    )
                )

            return {
                "ok": True,
                "boss_battle_count": (
                    len(results)
                ),
                "boss_battles": results,
                "provider_called": False,
                "estimated_cost_usd": 0,
            }