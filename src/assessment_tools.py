from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    Assessment,
    GradeGoal,
    Subject,
)


ALLOWED_ASSESSMENT_TYPES = {
    "exam",
    "assignment",
    "project",
    "presentation",
    "participation",
    "quiz",
    "practice",
    "other",
}

ALLOWED_ASSESSMENT_STATUSES = {
    "pending",
    "completed",
    "cancelled",
}


def clean_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()

    return cleaned or None


def parse_optional_date(
    value: str | None,
) -> date | None:
    if value is None or not value.strip():
        return None

    return date.fromisoformat(
        value.strip()
    )


def assessment_to_dict(
    assessment: Assessment,
    subject_name: str | None = None,
) -> dict[str, Any]:

    contribution = None

    if assessment.obtained_grade is not None:
        normalized_grade = (
            assessment.obtained_grade
            / assessment.maximum_grade
        )

        contribution = round(
            normalized_grade
            * assessment.weight_percentage,
            4,
        )

    return {
        "id": assessment.id,
        "subject_id": assessment.subject_id,
        "subject_name": subject_name,
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
        "maximum_grade": (
            assessment.maximum_grade
        ),
        "obtained_grade": (
            assessment.obtained_grade
        ),
        "status": assessment.status,
        "description": assessment.description,
        "professor_feedback": (
            assessment.professor_feedback
        ),
        "notes": assessment.notes,
        "weighted_contribution_percentage": (
            contribution
        ),
        "created_at": (
            assessment.created_at.isoformat()
            if assessment.created_at
            else None
        ),
        "updated_at": (
            assessment.updated_at.isoformat()
            if assessment.updated_at
            else None
        ),
    }


def register_assessment_tools(mcp) -> None:

    @mcp.tool()
    def create_assessment(
        subject_id: int,
        title: str,
        assessment_type: str,
        weight_percentage: float,
        assessment_date: str | None = None,
        maximum_grade: float = 10.0,
        description: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Registra una evaluación de una asignatura."""

        clean_title = title.strip()

        if not clean_title:
            return {
                "ok": False,
                "error": (
                    "El título no puede estar vacío"
                ),
            }

        clean_type = (
            assessment_type
            .strip()
            .casefold()
        )

        if clean_type not in ALLOWED_ASSESSMENT_TYPES:
            return {
                "ok": False,
                "error": (
                    "assessment_type debe ser exam, "
                    "assignment, project, presentation, "
                    "participation, quiz, practice u other"
                ),
            }

        if (
            weight_percentage <= 0
            or weight_percentage > 100
        ):
            return {
                "ok": False,
                "error": (
                    "weight_percentage debe ser "
                    "mayor que 0 y menor o igual que 100"
                ),
            }

        if maximum_grade <= 0:
            return {
                "ok": False,
                "error": (
                    "maximum_grade debe ser mayor que 0"
                ),
            }

        try:
            parsed_date = parse_optional_date(
                assessment_date
            )
        except ValueError:
            return {
                "ok": False,
                "error": (
                    "assessment_date debe usar YYYY-MM-DD"
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

            existing_assessments = (
                session.scalars(
                    select(Assessment).where(
                        Assessment.subject_id
                        == subject_id,
                        Assessment.status
                        != "cancelled",
                    )
                ).all()
            )

            current_weight = sum(
                assessment.weight_percentage
                for assessment
                in existing_assessments
            )

            projected_weight = (
                current_weight
                + weight_percentage
            )

            if projected_weight > 100.0001:
                return {
                    "ok": False,
                    "error": (
                        "El peso total de las evaluaciones "
                        "superaría el 100 %"
                    ),
                    "current_weight_percentage": (
                        round(current_weight, 4)
                    ),
                    "attempted_total_percentage": (
                        round(projected_weight, 4)
                    ),
                }

            assessment = Assessment(
                subject_id=subject_id,
                title=clean_title,
                assessment_type=clean_type,
                assessment_date=parsed_date,
                weight_percentage=(
                    weight_percentage
                ),
                maximum_grade=maximum_grade,
                obtained_grade=None,
                status="pending",
                description=clean_optional_text(
                    description
                ),
                notes=clean_optional_text(
                    notes
                ),
                updated_at=datetime.utcnow(),
            )

            session.add(assessment)
            session.commit()
            session.refresh(assessment)

            return {
                "ok": True,
                "assessment": assessment_to_dict(
                    assessment,
                    subject_name=subject.name,
                ),
                "subject_total_weight_percentage": (
                    round(projected_weight, 4)
                ),
                "remaining_weight_percentage": (
                    round(
                        100 - projected_weight,
                        4,
                    )
                ),
            }

    @mcp.tool()
    def record_assessment_grade(
        assessment_id: int,
        obtained_grade: float,
        professor_feedback: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Registra la nota obtenida."""

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

            if (
                obtained_grade < 0
                or obtained_grade
                > assessment.maximum_grade
            ):
                return {
                    "ok": False,
                    "error": (
                        "La nota debe estar entre 0 y "
                        f"{assessment.maximum_grade}"
                    ),
                }

            assessment.obtained_grade = (
                obtained_grade
            )

            assessment.status = "completed"

            if professor_feedback is not None:
                assessment.professor_feedback = (
                    clean_optional_text(
                        professor_feedback
                    )
                )

            if notes is not None:
                assessment.notes = (
                    clean_optional_text(notes)
                )

            assessment.updated_at = (
                datetime.utcnow()
            )

            session.commit()
            session.refresh(assessment)

            subject = session.get(
                Subject,
                assessment.subject_id,
            )

            return {
                "ok": True,
                "assessment": assessment_to_dict(
                    assessment,
                    subject_name=(
                        subject.name
                        if subject
                        else None
                    ),
                ),
            }

    @mcp.tool()
    def list_assessments(
        subject_id: int,
        status: str | None = None,
    ) -> dict:
        """Lista las evaluaciones de una asignatura."""

        clean_status = None

        if status is not None and status.strip():
            clean_status = (
                status.strip().casefold()
            )

            if (
                clean_status
                not in ALLOWED_ASSESSMENT_STATUSES
            ):
                return {
                    "ok": False,
                    "error": (
                        "status debe ser pending, "
                        "completed o cancelled"
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

            statement = select(
                Assessment
            ).where(
                Assessment.subject_id
                == subject_id
            )

            if clean_status is not None:
                statement = statement.where(
                    Assessment.status
                    == clean_status
                )

            statement = statement.order_by(
                Assessment.assessment_date.is_(None),
                Assessment.assessment_date.asc(),
                Assessment.id.asc(),
            )

            assessments = session.scalars(
                statement
            ).all()

            total_weight = sum(
                assessment.weight_percentage
                for assessment in assessments
                if assessment.status
                != "cancelled"
            )

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "result_count": len(
                    assessments
                ),
                "total_weight_percentage": round(
                    total_weight,
                    4,
                ),
                "remaining_weight_percentage": round(
                    100 - total_weight,
                    4,
                ),
                "assessments": [
                    assessment_to_dict(
                        assessment,
                        subject_name=subject.name,
                    )
                    for assessment in assessments
                ],
            }

    @mcp.tool()
    def set_grade_goal(
        subject_id: int,
        target_grade: float,
        maximum_grade: float = 10.0,
    ) -> dict:
        """Define la nota objetivo de una asignatura."""

        if maximum_grade <= 0:
            return {
                "ok": False,
                "error": (
                    "maximum_grade debe ser mayor que 0"
                ),
            }

        if (
            target_grade < 0
            or target_grade > maximum_grade
        ):
            return {
                "ok": False,
                "error": (
                    "target_grade debe estar entre "
                    f"0 y {maximum_grade}"
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

            goal = session.scalar(
                select(GradeGoal).where(
                    GradeGoal.subject_id
                    == subject_id
                )
            )

            if goal is None:
                goal = GradeGoal(
                    subject_id=subject_id,
                    target_grade=target_grade,
                    maximum_grade=maximum_grade,
                    updated_at=datetime.utcnow(),
                )

                session.add(goal)

            else:
                goal.target_grade = target_grade
                goal.maximum_grade = maximum_grade
                goal.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(goal)

            return {
                "ok": True,
                "goal": {
                    "id": goal.id,
                    "subject_id": subject_id,
                    "subject_name": (
                        subject.name
                    ),
                    "target_grade": (
                        goal.target_grade
                    ),
                    "maximum_grade": (
                        goal.maximum_grade
                    ),
                },
            }