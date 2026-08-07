from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    Assessment,
    Professor,
    ProfessorPreference,
    RubricCriterion,
    Subject,
)


def register_assignment_preparation_tools(mcp) -> None:

    @mcp.tool()
    def build_assignment_preparation_context(
        subject_id: int,
        assessment_id: int,
        professor_id: int | None = None,
    ) -> dict:
        """
        Reúne todo lo que UniCore sabe antes de preparar
        una entrega o evaluación.
        """

        with SessionLocal() as session:
            subject = session.get(
                Subject,
                subject_id,
            )

            if subject is None:
                return {
                    "ok": False,
                    "error": "La asignatura no existe",
                }

            assessment = session.get(
                Assessment,
                assessment_id,
            )

            if (
                assessment is None
                or assessment.subject_id
                != subject_id
            ):
                return {
                    "ok": False,
                    "error": (
                        "La evaluación no existe "
                        "en esta asignatura"
                    ),
                }

            professor = None

            if professor_id is not None:
                professor = session.get(
                    Professor,
                    professor_id,
                )

                if professor is None:
                    return {
                        "ok": False,
                        "error": "El profesor no existe",
                    }

                if professor.subject_id != subject_id:
                    return {
                        "ok": False,
                        "error": (
                            "El profesor no pertenece "
                            "a esta asignatura"
                        ),
                    }

            preference_statement = select(
                ProfessorPreference
            ).where(
                ProfessorPreference.subject_id
                == subject_id
            )

            if professor_id is not None:
                preference_statement = (
                    preference_statement.where(
                        ProfessorPreference.professor_id
                        == professor_id
                    )
                )

            preferences = session.scalars(
                preference_statement.order_by(
                    ProfessorPreference.importance.desc(),
                    ProfessorPreference.confidence.desc(),
                )
            ).all()

            rubric_criteria = session.scalars(
                select(RubricCriterion)
                .where(
                    RubricCriterion.subject_id
                    == subject_id,
                    RubricCriterion.assessment_id
                    == assessment_id,
                )
                .order_by(
                    RubricCriterion.id.asc()
                )
            ).all()

            previous_feedback = session.scalars(
                select(Assessment)
                .where(
                    Assessment.subject_id
                    == subject_id,
                    Assessment.status
                    == "completed",
                    Assessment.professor_feedback
                    .is_not(None),
                    Assessment.id
                    != assessment_id,
                )
                .order_by(
                    Assessment.updated_at.desc()
                )
                .limit(10)
            ).all()

            related_tasks = session.scalars(
                select(AcademicTask)
                .where(
                    AcademicTask.subject_id
                    == subject_id,
                    AcademicTask.status.notin_(
                        ["completed", "cancelled"]
                    ),
                )
                .order_by(
                    AcademicTask.priority.desc(),
                    AcademicTask.due_date.asc(),
                )
            ).all()

            checklist = []

            for criterion in rubric_criteria:
                checklist.append({
                    "type": "rubric",
                    "title": criterion.title,
                    "instruction": (
                        criterion.description
                        or (
                            "Asegúrate de cumplir "
                            "este criterio de la rúbrica."
                        )
                    ),
                    "weight_percentage": (
                        criterion.weight_percentage
                    ),
                })

            for preference in preferences:
                if preference.importance >= 4:
                    checklist.append({
                        "type": "professor_preference",
                        "title": preference.category,
                        "instruction": (
                            preference.preference
                        ),
                        "importance": (
                            preference.importance
                        ),
                        "confidence": (
                            preference.confidence
                        ),
                    })

            for old_assessment in previous_feedback:
                checklist.append({
                    "type": "previous_feedback",
                    "title": (
                        f"Feedback anterior: "
                        f"{old_assessment.title}"
                    ),
                    "instruction": (
                        old_assessment.professor_feedback
                    ),
                })

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "assessment": {
                    "id": assessment.id,
                    "title": assessment.title,
                    "assessment_type": (
                        assessment.assessment_type
                    ),
                    "assessment_date": (
                        assessment.assessment_date.isoformat()
                        if assessment.assessment_date
                        else None
                    ),
                    "weight_percentage": (
                        assessment.weight_percentage
                    ),
                    "description": (
                        assessment.description
                    ),
                    "notes": assessment.notes,
                },
                "professor": (
                    {
                        "id": professor.id,
                        "name": professor.name,
                    }
                    if professor
                    else None
                ),
                "professor_preferences": [
                    {
                        "id": item.id,
                        "category": item.category,
                        "preference": item.preference,
                        "importance": item.importance,
                        "confidence": item.confidence,
                        "source_type": item.source_type,
                    }
                    for item in preferences
                ],
                "rubric": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "description": item.description,
                        "weight_percentage": (
                            item.weight_percentage
                        ),
                        "maximum_points": (
                            item.maximum_points
                        ),
                    }
                    for item in rubric_criteria
                ],
                "previous_feedback": [
                    {
                        "assessment_id": item.id,
                        "assessment_title": (
                            item.title
                        ),
                        "obtained_grade": (
                            item.obtained_grade
                        ),
                        "feedback": (
                            item.professor_feedback
                        ),
                    }
                    for item in previous_feedback
                ],
                "related_pending_tasks": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "priority": item.priority,
                        "due_date": (
                            item.due_date.isoformat()
                            if item.due_date
                            else None
                        ),
                        "progress_percentage": (
                            item.progress_percentage
                        ),
                    }
                    for item in related_tasks
                ],
                "preparation_checklist": checklist,
                "checklist_item_count": len(
                    checklist
                ),
                "provider_called": False,
                "estimated_cost_usd": 0,
            }