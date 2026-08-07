from datetime import datetime

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    Assessment,
    Professor,
    ProfessorPreference,
    RubricCriterion,
    Subject,
)


ALLOWED_PREFERENCE_CATEGORIES = {
    "structure",
    "writing_style",
    "depth",
    "sources",
    "format",
    "presentation",
    "analysis",
    "participation",
    "common_mistakes",
    "other",
}

ALLOWED_SOURCE_TYPES = {
    "direct_instruction",
    "rubric",
    "feedback",
    "class",
    "observation",
    "other",
}


def clean_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def preference_to_dict(
    preference: ProfessorPreference,
    professor_name: str | None = None,
    subject_name: str | None = None,
) -> dict:
    return {
        "id": preference.id,
        "professor_id": preference.professor_id,
        "professor_name": professor_name,
        "subject_id": preference.subject_id,
        "subject_name": subject_name,
        "category": preference.category,
        "preference": preference.preference,
        "importance": preference.importance,
        "source_type": preference.source_type,
        "source_reference": preference.source_reference,
        "confidence": preference.confidence,
        "created_at": (
            preference.created_at.isoformat()
            if preference.created_at
            else None
        ),
        "updated_at": (
            preference.updated_at.isoformat()
            if preference.updated_at
            else None
        ),
    }


def rubric_to_dict(
    criterion: RubricCriterion,
) -> dict:
    return {
        "id": criterion.id,
        "subject_id": criterion.subject_id,
        "professor_id": criterion.professor_id,
        "assessment_id": criterion.assessment_id,
        "title": criterion.title,
        "description": criterion.description,
        "weight_percentage": criterion.weight_percentage,
        "maximum_points": criterion.maximum_points,
        "notes": criterion.notes,
        "created_at": (
            criterion.created_at.isoformat()
            if criterion.created_at
            else None
        ),
        "updated_at": (
            criterion.updated_at.isoformat()
            if criterion.updated_at
            else None
        ),
    }


def register_professor_rubric_tools(mcp) -> None:

    @mcp.tool()
    def add_professor_preference(
        professor_id: int,
        subject_id: int,
        category: str,
        preference: str,
        importance: int = 3,
        source_type: str = "observation",
        source_reference: str | None = None,
        confidence: int = 3,
    ) -> dict:
        """Guarda una preferencia o criterio observado del profesor."""

        clean_preference = preference.strip()

        if not clean_preference:
            return {
                "ok": False,
                "error": "preference no puede estar vacío",
            }

        clean_category = category.strip().casefold()

        if clean_category not in ALLOWED_PREFERENCE_CATEGORIES:
            return {
                "ok": False,
                "error": (
                    "category no compatible"
                ),
            }

        clean_source_type = source_type.strip().casefold()

        if clean_source_type not in ALLOWED_SOURCE_TYPES:
            return {
                "ok": False,
                "error": (
                    "source_type no compatible"
                ),
            }

        if importance < 1 or importance > 5:
            return {
                "ok": False,
                "error": "importance debe estar entre 1 y 5",
            }

        if confidence < 1 or confidence > 5:
            return {
                "ok": False,
                "error": "confidence debe estar entre 1 y 5",
            }

        with SessionLocal() as session:
            professor = session.get(
                Professor,
                professor_id,
            )

            if professor is None:
                return {
                    "ok": False,
                    "error": "El profesor no existe",
                }

            subject = session.get(
                Subject,
                subject_id,
            )

            if subject is None:
                return {
                    "ok": False,
                    "error": "La asignatura no existe",
                }

            if professor.subject_id != subject_id:
                return {
                    "ok": False,
                    "error": (
                        "El profesor no pertenece "
                        "a esta asignatura"
                    ),
                }

            record = ProfessorPreference(
                professor_id=professor_id,
                subject_id=subject_id,
                category=clean_category,
                preference=clean_preference,
                importance=importance,
                source_type=clean_source_type,
                source_reference=clean_optional_text(
                    source_reference
                ),
                confidence=confidence,
                updated_at=datetime.utcnow(),
            )

            session.add(record)
            session.commit()
            session.refresh(record)

            return {
                "ok": True,
                "preference": preference_to_dict(
                    record,
                    professor_name=professor.name,
                    subject_name=subject.name,
                ),
            }

    @mcp.tool()
    def list_professor_preferences(
        professor_id: int,
        subject_id: int | None = None,
    ) -> dict:
        """Lista lo que UniCore sabe sobre un profesor."""

        with SessionLocal() as session:
            professor = session.get(
                Professor,
                professor_id,
            )

            if professor is None:
                return {
                    "ok": False,
                    "error": "El profesor no existe",
                }

            statement = select(
                ProfessorPreference
            ).where(
                ProfessorPreference.professor_id
                == professor_id
            )

            if subject_id is not None:
                statement = statement.where(
                    ProfessorPreference.subject_id
                    == subject_id
                )

            preferences = session.scalars(
                statement.order_by(
                    ProfessorPreference.importance.desc(),
                    ProfessorPreference.confidence.desc(),
                    ProfessorPreference.id.asc(),
                )
            ).all()

            return {
                "ok": True,
                "professor": {
                    "id": professor.id,
                    "name": professor.name,
                },
                "result_count": len(preferences),
                "preferences": [
                    preference_to_dict(item)
                    for item in preferences
                ],
            }

    @mcp.tool()
    def add_rubric_criterion(
        subject_id: int,
        title: str,
        professor_id: int | None = None,
        assessment_id: int | None = None,
        description: str | None = None,
        weight_percentage: float | None = None,
        maximum_points: float | None = None,
        notes: str | None = None,
    ) -> dict:
        """Añade un criterio de rúbrica."""

        clean_title = title.strip()

        if not clean_title:
            return {
                "ok": False,
                "error": "El título no puede estar vacío",
            }

        if (
            weight_percentage is not None
            and (
                weight_percentage < 0
                or weight_percentage > 100
            )
        ):
            return {
                "ok": False,
                "error": (
                    "weight_percentage debe estar entre 0 y 100"
                ),
            }

        if (
            maximum_points is not None
            and maximum_points <= 0
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_points debe ser mayor que 0"
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
                    "error": "La asignatura no existe",
                }

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

            if assessment_id is not None:
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

                if assessment.subject_id != subject_id:
                    return {
                        "ok": False,
                        "error": (
                            "La evaluación pertenece "
                            "a otra asignatura"
                        ),
                    }

            criterion = RubricCriterion(
                subject_id=subject_id,
                professor_id=professor_id,
                assessment_id=assessment_id,
                title=clean_title,
                description=clean_optional_text(
                    description
                ),
                weight_percentage=weight_percentage,
                maximum_points=maximum_points,
                notes=clean_optional_text(notes),
                updated_at=datetime.utcnow(),
            )

            session.add(criterion)
            session.commit()
            session.refresh(criterion)

            return {
                "ok": True,
                "criterion": rubric_to_dict(
                    criterion
                ),
            }

    @mcp.tool()
    def list_rubric_criteria(
        subject_id: int,
        assessment_id: int | None = None,
    ) -> dict:
        """Lista criterios de rúbrica."""

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

            statement = select(
                RubricCriterion
            ).where(
                RubricCriterion.subject_id
                == subject_id
            )

            if assessment_id is not None:
                statement = statement.where(
                    RubricCriterion.assessment_id
                    == assessment_id
                )

            criteria = session.scalars(
                statement.order_by(
                    RubricCriterion.id.asc()
                )
            ).all()

            total_weight = sum(
                item.weight_percentage or 0
                for item in criteria
            )

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "assessment_id": assessment_id,
                "result_count": len(criteria),
                "total_rubric_weight_percentage": round(
                    total_weight,
                    4,
                ),
                "criteria": [
                    rubric_to_dict(item)
                    for item in criteria
                ],
            }