from datetime import (
    date,
    datetime,
)

from sqlalchemy import select

from src.database.connection import (
    SessionLocal,
)

from src.database.models import (
    AcademicTask,
    Assessment,
    KnowledgeConcept,
    ReviewItem,
    Subject,
)

from src.task_planner_tools import (
    calculate_task_urgency,
)


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def recommendation_priority_label(
    score: float,
) -> str:
    if score >= 80:
        return "critical"

    if score >= 60:
        return "high"

    if score >= 40:
        return "medium"

    return "low"


def task_recommendation(
    task: AcademicTask,
    subject_name: str | None,
    today: date,
) -> dict:
    """
    Convierte una tarea pendiente en una posible acción.
    """

    urgency = calculate_task_urgency(
        task,
        today,
    )

    raw_score = float(
        urgency[
            "planning_score"
        ]
    )

    score = clamp(
        raw_score,
        0,
        100,
    )

    remaining_minutes = urgency.get(
        "remaining_minutes"
    )

    if (
        remaining_minutes is None
        or remaining_minutes <= 0
    ):
        remaining_minutes = 30

    suggested_minutes = int(
        clamp(
            remaining_minutes,
            15,
            60,
        )
    )

    reasons = []

    days = urgency.get(
        "days_until_due"
    )

    if days is not None:
        if days < 0:
            reasons.append(
                "La tarea está vencida."
            )

        elif days == 0:
            reasons.append(
                "La tarea vence hoy."
            )

        elif days == 1:
            reasons.append(
                "La tarea vence mañana."
            )

        elif days <= 3:
            reasons.append(
                f"La tarea vence en {days} días."
            )

    if task.priority >= 4:
        reasons.append(
            f"Tiene prioridad {task.priority}/5."
        )

    if task.progress_percentage < 50:
        reasons.append(
            "Todavía queda una parte importante por completar."
        )

    elif task.progress_percentage < 100:
        reasons.append(
            f"Está al {task.progress_percentage}% de progreso."
        )

    return {
        "type": "task",
        "source_id": task.id,
        "subject_id": task.subject_id,
        "subject_name": subject_name,
        "title": task.title,
        "score": round(
            score,
            2,
        ),
        "priority": (
            recommendation_priority_label(
                score
            )
        ),
        "suggested_minutes": (
            suggested_minutes
        ),
        "reasons": reasons,
        "action": (
            "Avanza esta tarea durante "
            f"{suggested_minutes} minutos."
        ),
        "metadata": {
            "task_type": task.task_type,
            "status": task.status,
            "priority_value": task.priority,
            "due_date": (
                task.due_date.isoformat()
                if task.due_date
                else None
            ),
            "progress_percentage": (
                task.progress_percentage
            ),
            "remaining_minutes": (
                remaining_minutes
            ),
        },
    }


def review_recommendation(
    review: ReviewItem,
    subject_name: str,
    now: datetime,
) -> dict:
    """
    Convierte un repaso pendiente en una acción.
    """

    overdue_hours = max(
        0,
        (
            now
            - review.next_review_at
        ).total_seconds()
        / 3600,
    )

    overdue_days = (
        overdue_hours
        / 24
    )

    score = (
        40
        + review.priority * 8
        + min(
            25,
            overdue_days * 5,
        )
        + min(
            15,
            review.incorrect_count * 4,
        )
    )

    score = clamp(
        score,
        0,
        100,
    )

    suggested_minutes = 15

    reasons = [
        "Este repaso ya está pendiente."
    ]

    if review.incorrect_count >= 2:
        reasons.append(
            "Ha generado varios errores anteriormente."
        )

    if review.priority >= 4:
        reasons.append(
            "Tiene prioridad alta dentro del sistema de repaso."
        )

    if review.correct_streak == 0:
        reasons.append(
            "Todavía no tiene una racha de respuestas correctas."
        )

    return {
        "type": "review",
        "source_id": review.id,
        "subject_id": review.subject_id,
        "subject_name": subject_name,
        "title": (
            f"Repasar: {review.topic}"
        ),
        "score": round(
            score,
            2,
        ),
        "priority": (
            recommendation_priority_label(
                score
            )
        ),
        "suggested_minutes": (
            suggested_minutes
        ),
        "reasons": reasons,
        "action": (
            f"Repasa {review.topic} "
            f"durante {suggested_minutes} minutos."
        ),
        "metadata": {
            "topic": review.topic,
            "review_priority": (
                review.priority
            ),
            "incorrect_count": (
                review.incorrect_count
            ),
            "correct_streak": (
                review.correct_streak
            ),
            "next_review_at": (
                review.next_review_at
                .isoformat()
            ),
        },
    }


def concept_recommendation(
    concept: KnowledgeConcept,
    subject_name: str,
) -> dict:
    """
    Convierte un concepto débil o en desarrollo
    en una posible acción de estudio.
    """

    mastery = (
        concept.mastery_percentage
    )

    if mastery is None:
        score = 35

    else:
        score = (
            80
            - mastery * 0.5
        )

    if concept.status == "weak":
        score += 20

    elif concept.status == "developing":
        score += 8

    elif concept.status == "unassessed":
        score += 5

    score = clamp(
        score,
        0,
        100,
    )

    suggested_minutes = (
        25
        if concept.status
        == "weak"
        else 20
    )

    reasons = []

    if concept.status == "weak":
        reasons.append(
            "El Knowledge Map identifica este concepto como débil."
        )

    elif concept.status == "developing":
        reasons.append(
            "El concepto todavía está en desarrollo."
        )

    elif concept.status == "unassessed":
        reasons.append(
            "Hay exposición al tema, pero todavía no suficiente evidencia evaluada."
        )

    if (
        mastery is not None
        and mastery < 60
    ):
        reasons.append(
            f"Dominio actual estimado: {mastery:.1f}%."
        )

    if (
        concept.assessed_evidence_count
        <= 1
    ):
        reasons.append(
            "Hay poca evidencia evaluada, por lo que conviene comprobar el dominio."
        )

    return {
        "type": "knowledge",
        "source_id": concept.id,
        "subject_id": concept.subject_id,
        "subject_name": subject_name,
        "title": (
            f"Trabajar: {concept.name}"
        ),
        "score": round(
            score,
            2,
        ),
        "priority": (
            recommendation_priority_label(
                score
            )
        ),
        "suggested_minutes": (
            suggested_minutes
        ),
        "reasons": reasons,
        "action": (
            f"Estudia o practica {concept.name} "
            f"durante {suggested_minutes} minutos."
        ),
        "metadata": {
            "concept": concept.name,
            "mastery_percentage": (
                mastery
            ),
            "status": (
                concept.status
            ),
            "evidence_count": (
                concept.evidence_count
            ),
            "assessed_evidence_count": (
                concept.assessed_evidence_count
            ),
            "exposure_minutes": (
                concept.exposure_minutes
            ),
        },
    }


def assessment_recommendation(
    assessment: Assessment,
    subject_name: str,
    today: date,
) -> dict | None:
    """
    Convierte una evaluación próxima
    en una acción de preparación.
    """

    if (
        assessment.assessment_date
        is None
    ):
        return None

    days_remaining = (
        assessment.assessment_date
        - today
    ).days

    if days_remaining < 0:
        return None

    if days_remaining > 21:
        return None

    if days_remaining == 0:
        urgency = 80

    elif days_remaining == 1:
        urgency = 70

    elif days_remaining <= 3:
        urgency = 60

    elif days_remaining <= 7:
        urgency = 45

    elif days_remaining <= 14:
        urgency = 30

    else:
        urgency = 15

    weight_points = min(
        20,
        assessment.weight_percentage
        * 0.4,
    )

    exam_bonus = (
        10
        if assessment.assessment_type
        == "exam"
        else 0
    )

    score = (
        urgency
        + weight_points
        + exam_bonus
    )

    score = clamp(
        score,
        0,
        100,
    )

    if days_remaining <= 3:
        suggested_minutes = 40
    elif days_remaining <= 7:
        suggested_minutes = 30
    else:
        suggested_minutes = 20

    reasons = [
        (
            f"{assessment.title} es en "
            f"{days_remaining} día(s)."
        )
    ]

    if (
        assessment.weight_percentage
        >= 30
    ):
        reasons.append(
            (
                "Tiene un peso importante "
                f"({assessment.weight_percentage:.0f}%)."
            )
        )

    if (
        assessment.assessment_type
        == "exam"
    ):
        reasons.append(
            "Es un examen y conviene preparar el contenido con antelación."
        )

    return {
        "type": "assessment",
        "source_id": assessment.id,
        "subject_id": assessment.subject_id,
        "subject_name": subject_name,
        "title": (
            f"Preparar: {assessment.title}"
        ),
        "score": round(
            score,
            2,
        ),
        "priority": (
            recommendation_priority_label(
                score
            )
        ),
        "suggested_minutes": (
            suggested_minutes
        ),
        "reasons": reasons,
        "action": (
            f"Dedica {suggested_minutes} minutos "
            f"a preparar {assessment.title}."
        ),
        "metadata": {
            "assessment_type": (
                assessment.assessment_type
            ),
            "assessment_date": (
                assessment.assessment_date
                .isoformat()
            ),
            "days_remaining": (
                days_remaining
            ),
            "weight_percentage": (
                assessment.weight_percentage
            ),
        },
    }


def fit_recommendations_to_time(
    recommendations: list[dict],
    available_minutes: int,
    maximum_actions: int,
) -> list[dict]:
    """
    Selecciona acciones hasta llenar aproximadamente
    el tiempo disponible.

    No corta una acción por debajo de 10 minutos.
    """

    selected = []

    remaining = (
        available_minutes
    )

    for item in recommendations:
        if (
            len(selected)
            >= maximum_actions
        ):
            break

        if remaining < 10:
            break

        suggested = item[
            "suggested_minutes"
        ]

        allocated = min(
            suggested,
            remaining,
        )

        if allocated < 10:
            continue

        selected_item = {
            **item,
            "allocated_minutes": int(
                allocated
            ),
        }

        selected.append(
            selected_item
        )

        remaining -= int(
            allocated
        )

    return selected


def build_decision_plan(
    available_minutes: int = 45,
    subject_id: int | None = None,
    maximum_actions: int = 3,
) -> dict:
    """
    Decide qué debería hacer el estudiante ahora.

    Todo se calcula localmente.
    No usa IA.
    """

    if (
        available_minutes < 10
        or available_minutes > 480
    ):
        return {
            "ok": False,
            "error": (
                "available_minutes debe estar "
                "entre 10 y 480"
            ),
        }

    if (
        maximum_actions < 1
        or maximum_actions > 10
    ):
        return {
            "ok": False,
            "error": (
                "maximum_actions debe estar "
                "entre 1 y 10"
            ),
        }

    today = date.today()
    now = datetime.now()

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
            select(
                Subject
            )
        ).all()

        subject_names = {
            subject.id: subject.name
            for subject in subjects
        }

        task_statement = (
            select(
                AcademicTask
            )
            .where(
                AcademicTask.status.notin_(
                    [
                        "completed",
                        "cancelled",
                    ]
                )
            )
        )

        review_statement = (
            select(
                ReviewItem
            )
            .where(
                ReviewItem.status
                != "mastered",
                ReviewItem.next_review_at
                <= now,
            )
        )

        concept_statement = (
            select(
                KnowledgeConcept
            )
            .where(
                KnowledgeConcept.status.in_(
                    [
                        "weak",
                        "developing",
                        "unassessed",
                    ]
                )
            )
        )

        assessment_statement = (
            select(
                Assessment
            )
            .where(
                Assessment.status
                == "pending"
            )
        )

        if subject_id is not None:
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

            concept_statement = (
                concept_statement.where(
                    KnowledgeConcept.subject_id
                    == subject_id
                )
            )

            assessment_statement = (
                assessment_statement.where(
                    Assessment.subject_id
                    == subject_id
                )
            )

        tasks = session.scalars(
            task_statement
        ).all()

        reviews = session.scalars(
            review_statement
        ).all()

        concepts = session.scalars(
            concept_statement
        ).all()

        assessments = session.scalars(
            assessment_statement
        ).all()

        recommendations = []

        for task in tasks:
            recommendations.append(
                task_recommendation(
                    task,
                    subject_names.get(
                        task.subject_id
                    ),
                    today,
                )
            )

        for review in reviews:
            recommendations.append(
                review_recommendation(
                    review,
                    subject_names.get(
                        review.subject_id,
                        "Asignatura",
                    ),
                    now,
                )
            )

        for concept in concepts:
            recommendations.append(
                concept_recommendation(
                    concept,
                    subject_names.get(
                        concept.subject_id,
                        "Asignatura",
                    ),
                )
            )

        for assessment in assessments:
            recommendation = (
                assessment_recommendation(
                    assessment,
                    subject_names.get(
                        assessment.subject_id,
                        "Asignatura",
                    ),
                    today,
                )
            )

            if (
                recommendation
                is not None
            ):
                recommendations.append(
                    recommendation
                )

        recommendations.sort(
            key=lambda item: (
                -item["score"],
                item["suggested_minutes"],
                item["type"],
            )
        )

        selected = (
            fit_recommendations_to_time(
                recommendations,
                available_minutes,
                maximum_actions,
            )
        )

        allocated_minutes = sum(
            item["allocated_minutes"]
            for item in selected
        )

        remaining_minutes = (
            available_minutes
            - allocated_minutes
        )

        if selected:
            top = selected[0]

            headline = (
                f"Empieza por: "
                f"{top['title']}"
            )
        else:
            headline = (
                "No hay una prioridad académica "
                "urgente detectada."
            )

        return {
            "ok": True,
            "generated_for_date": (
                today.isoformat()
            ),
            "subject": (
                {
                    "id": selected_subject.id,
                    "name": selected_subject.name,
                }
                if selected_subject
                else None
            ),
            "available_minutes": (
                available_minutes
            ),
            "headline": headline,
            "recommended_action_count": (
                len(selected)
            ),
            "allocated_minutes": (
                allocated_minutes
            ),
            "remaining_minutes": (
                remaining_minutes
            ),
            "actions": selected,
            "candidate_count": (
                len(recommendations)
            ),
            "scoring_note": (
                "La puntuación es una prioridad interna "
                "basada en urgencia, tareas, repasos, "
                "evaluaciones y Knowledge Map. "
                "No es una predicción de rendimiento."
            ),
            "cost": {
                "ai_used": False,
                "estimated_cost": 0,
            },
        }


def register_decision_engine(
    mcp,
) -> None:
    """
    Expone una sola Tool pública.

    Es una Tool porque recibe parámetros dinámicos
    y ejecuta un cálculo de planificación.
    """

    @mcp.tool()
    def recommend_next_actions(
        available_minutes: int = 45,
        subject_id: int | None = None,
        maximum_actions: int = 3,
    ) -> dict:
        """
        Decide qué debería hacer el estudiante ahora
        con el tiempo disponible.

        Coste IA: 0.
        """

        return build_decision_plan(
            available_minutes=(
                available_minutes
            ),
            subject_id=subject_id,
            maximum_actions=(
                maximum_actions
            ),
        )