import json
from datetime import datetime

from sqlalchemy import select

from src.academic_risk_tools import (
    build_subject_risk,
)
from src.academic_task_tools import (
    task_to_dict,
)
from src.analytics_tools import (
    build_learning_analytics,
)
from src.assessment_tools import (
    assessment_to_dict,
)
from src.class_session_tools import (
    class_session_to_dict,
    load_related_entities,
)
from src.database.connection import (
    SessionLocal,
)
from src.database.models import (
    AcademicTask,
    Assessment,
    ClassSession,
    Document,
    Professor,
    ProfessorAssignment,
    ProfessorPreference,
    ReviewItem,
    RubricCriterion,
    StudyAttempt,
    StudySession,
    Subject,
)
from src.professor_rubric_tools import (
    preference_to_dict,
    rubric_to_dict,
)
from src.review_tools import (
    review_item_to_dict,
)
from src.study_progress_tools import (
    attempt_to_dict,
)
from src.study_session_tools import (
    study_session_to_dict,
)
from src.study_tools import (
    SUPPORTED_STUDY_MODES,
)
from src.task_planner_tools import (
    calculate_task_urgency,
)
from src.unicore_dashboard import (
    build_dashboard_data,
)


def _json(
    data,
) -> str:
    """
    Convierte datos Python a JSON legible.

    default=str evita problemas con fechas u
    otros tipos no serializables directamente.
    """

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _subject_exists(
    session,
    subject_id: int,
) -> Subject | None:
    """
    Devuelve la asignatura o None.
    """

    return session.get(
        Subject,
        subject_id,
    )


def _build_profile() -> dict:
    """
    Vista global mínima.

    Debe ser uno de los Resources más baratos
    para usar como primera consulta.
    """

    data = build_dashboard_data()

    if not data.get("ok"):
        return data

    hero = data.get(
        "hero",
        {},
    )

    metrics = data.get(
        "metrics",
        {},
    )

    return {
        "ok": True,
        "level": hero.get(
            "level"
        ),
        "total_xp": hero.get(
            "total_xp"
        ),
        "current_streak": hero.get(
            "current_streak"
        ),
        "longest_streak": hero.get(
            "longest_streak"
        ),
        "study_minutes_today": metrics.get(
            "study_minutes_today"
        ),
        "study_minutes_last_7_days": (
            metrics.get(
                "study_minutes_last_7_days"
            )
        ),
        "quiz_average_percentage": (
            metrics.get(
                "quiz_average_percentage"
            )
        ),
        "pending_task_count": metrics.get(
            "pending_task_count"
        ),
        "overdue_task_count": metrics.get(
            "overdue_task_count"
        ),
        "due_review_count": metrics.get(
            "due_review_count"
        ),
    }


def _build_today() -> dict:
    """
    Información global necesaria para responder:
    ¿qué merece atención hoy?
    """

    data = build_dashboard_data()

    if not data.get("ok"):
        return data

    metrics = data.get(
        "metrics",
        {},
    )

    missions = data.get(
        "missions",
        {},
    )

    return {
        "ok": True,
        "study_minutes_today": metrics.get(
            "study_minutes_today"
        ),
        "pending_task_count": metrics.get(
            "pending_task_count"
        ),
        "overdue_task_count": metrics.get(
            "overdue_task_count"
        ),
        "due_review_count": metrics.get(
            "due_review_count"
        ),
        "next_assessment": data.get(
            "next_assessment"
        ),
        "next_boss": data.get(
            "next_boss"
        ),
        "priorities": data.get(
            "priorities",
            [],
        )[:5],
        "missions": missions.get(
            "items",
            [],
        ),
    }


def _build_subjects() -> dict:
    """
    Lista compacta de asignaturas.
    """

    data = build_dashboard_data()

    if not data.get("ok"):
        return data

    compact = []

    for subject in data.get(
        "subjects",
        [],
    ):
        grade = subject.get(
            "grade",
            {},
        )

        compact.append({
            "id": subject.get(
                "id"
            ),
            "name": subject.get(
                "name"
            ),
            "xp": subject.get(
                "xp"
            ),
            "study_minutes": subject.get(
                "study_minutes"
            ),
            "quiz_average_percentage": (
                subject.get(
                    "quiz_average_percentage"
                )
            ),
            "current_grade": grade.get(
                "current_grade_out_of_10"
            ),
            "next_assessment": subject.get(
                "next_assessment"
            ),
        })

    return {
        "ok": True,
        "count": len(compact),
        "subjects": compact,
    }


def _build_subject(
    subject_id: int,
) -> dict:
    """
    Snapshot compacto de una asignatura.
    """

    data = build_dashboard_data(
        subject_id=subject_id
    )

    if not data.get("ok"):
        return data

    hero = data.get(
        "hero",
        {},
    )

    metrics = data.get(
        "metrics",
        {},
    )

    risk_result = build_subject_risk(
        subject_id
    )

    risk_summary = None

    if risk_result.get("ok"):
        risk_data = risk_result.get(
            "risk",
            {},
        )

        risk_summary = {
            "score": risk_data.get(
                "score"
            ),
            "level": risk_data.get(
                "level"
            ),
        }

    return {
        "ok": True,
        "subject": data.get(
            "subject"
        ),
        "level": hero.get(
            "level"
        ),
        "xp": hero.get(
            "total_xp"
        ),
        "current_streak": hero.get(
            "current_streak"
        ),
        "study_minutes_last_7_days": (
            metrics.get(
                "study_minutes_last_7_days"
            )
        ),
        "quiz_average_percentage": (
            metrics.get(
                "quiz_average_percentage"
            )
        ),
        "pending_task_count": metrics.get(
            "pending_task_count"
        ),
        "due_review_count": metrics.get(
            "due_review_count"
        ),
        "next_assessment": data.get(
            "next_assessment"
        ),
        "grade": data.get(
            "grade"
        ),
        "risk": risk_summary,
    }


def _build_subject_dashboard(
    subject_id: int,
) -> dict:
    """
    Dashboard conversacional compacto.
    """

    data = build_dashboard_data(
        subject_id=subject_id
    )

    if not data.get("ok"):
        return data

    return {
        "ok": True,
        "subject": data.get(
            "subject"
        ),
        "hero": data.get(
            "hero"
        ),
        "metrics": data.get(
            "metrics"
        ),
        "next_assessment": data.get(
            "next_assessment"
        ),
        "next_boss": data.get(
            "next_boss"
        ),
        "grade": data.get(
            "grade"
        ),
        "priorities": data.get(
            "priorities",
            [],
        )[:5],
        "missions": data.get(
            "missions"
        ),
    }


def _build_subject_analytics(
    subject_id: int,
) -> dict:
    """
    Analytics de una sola asignatura.
    """

    return build_learning_analytics(
        subject_id=subject_id,
        comparison_days=14,
    )


def _build_subject_risk(
    subject_id: int,
) -> dict:
    """
    Riesgo de una sola asignatura.
    """

    return build_subject_risk(
        subject_id
    )


def _build_subject_grade(
    subject_id: int,
) -> dict:
    """
    Estado de notas de una asignatura.
    """

    data = build_dashboard_data(
        subject_id=subject_id
    )

    if not data.get("ok"):
        return data

    return {
        "ok": True,
        "subject": data.get(
            "subject"
        ),
        "grade": data.get(
            "grade"
        ),
        "next_assessment": data.get(
            "next_assessment"
        ),
    }


def _build_tasks(
    subject_id: int | None = None,
) -> dict:
    """
    Tareas pendientes.

    Si subject_id es None devuelve todas.
    Si se indica subject_id devuelve las de
    una asignatura concreta.
    """

    today = datetime.now().date()

    with SessionLocal() as session:
        subject = None

        if subject_id is not None:
            subject = _subject_exists(
                session,
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
            AcademicTask
        ).where(
            AcademicTask.status.notin_(
                [
                    "completed",
                    "cancelled",
                ]
            )
        )

        if subject_id is not None:
            statement = statement.where(
                AcademicTask.subject_id
                == subject_id
            )

        tasks = session.scalars(
            statement
        ).all()

        result = []

        for task in tasks:
            task_subject = (
                session.get(
                    Subject,
                    task.subject_id,
                )
                if task.subject_id
                is not None
                else None
            )

            task_data = task_to_dict(
                task,
                subject_name=(
                    task_subject.name
                    if task_subject
                    else None
                ),
            )

            urgency = (
                calculate_task_urgency(
                    task,
                    today,
                )
            )

            result.append({
                "task": task_data,
                "planning": urgency,
            })

        result.sort(
            key=lambda item: (
                -item["planning"][
                    "planning_score"
                ],
                (
                    item["task"][
                        "due_date"
                    ]
                    is None
                ),
                item["task"][
                    "due_date"
                ]
                or "",
                item["task"]["id"],
            )
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
            "count": len(result),
            "tasks": result[:20],
        }


def _build_documents(
    subject_id: int | None = None,
) -> dict:
    """
    Catálogo compacto de documentos.

    No incluye extracted_text para evitar
    cargar miles de tokens sin necesidad.
    """

    with SessionLocal() as session:
        subject = None

        if subject_id is not None:
            subject = _subject_exists(
                session,
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
            Document
        )

        if subject_id is not None:
            statement = statement.where(
                Document.subject_id
                == subject_id
            )

        documents = session.scalars(
            statement.order_by(
                Document.created_at.desc()
            )
        ).all()

        result = []

        for document in documents:
            result.append({
                "id": document.id,
                "title": document.title,
                "file_type": (
                    document.file_type
                ),
                "document_type": (
                    document.document_type
                ),
                "academic_year": document.academic_year,
                "semester": document.semester,
                "professor_id": document.professor_id,
                "subject_id": (
                    document.subject_id
                ),
                "has_extracted_text": (
                    bool(
                        document.extracted_text
                    )
                ),
                "character_count": (
                    len(
                        document.extracted_text
                    )
                    if document.extracted_text
                    else 0
                ),
                "chunk_count": len(
                    document.chunks
                ),
                "created_at": (
                    document.created_at
                    .isoformat()
                    if document.created_at
                    else None
                ),
            })

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
            "count": len(result),
            "documents": result,
        }


def _build_subject_classes(
    subject_id: int,
) -> dict:
    """
    Timeline compacto de clases.

    Omite transcript y notes largas.
    """

    with SessionLocal() as session:
        subject = _subject_exists(
            session,
            subject_id,
        )

        if subject is None:
            return {
                "ok": False,
                "error": (
                    "La asignatura no existe"
                ),
            }

        classes = session.scalars(
            select(
                ClassSession
            )
            .where(
                ClassSession.subject_id
                == subject_id
            )
            .order_by(
                ClassSession.class_date.desc(),
                ClassSession.start_time.desc(),
                ClassSession.id.desc(),
            )
        ).all()

        result = []

        for class_session in classes:
            (
                related_subject,
                professor,
                document,
            ) = load_related_entities(
                session,
                class_session,
            )

            result.append(
                class_session_to_dict(
                    class_session,
                    subject=related_subject,
                    professor=professor,
                    document=document,
                    include_long_text=False,
                )
            )

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "academic_language": subject.academic_language,
                "academic_language_configured": subject.academic_language_configured,
            },
            "count": len(result),
            "classes": result[:30],
        }


def _build_subject_study(
    subject_id: int,
) -> dict:
    """
    Estado de estudio.

    Agrupa intentos de quiz y sesiones reales
    sin cargar preguntas completas.
    """

    with SessionLocal() as session:
        subject = _subject_exists(
            session,
            subject_id,
        )

        if subject is None:
            return {
                "ok": False,
                "error": (
                    "La asignatura no existe"
                ),
            }

        attempts = session.scalars(
            select(
                StudyAttempt
            )
            .where(
                StudyAttempt.subject_id
                == subject_id
            )
            .order_by(
                StudyAttempt.started_at.desc()
            )
        ).all()

        sessions = session.scalars(
            select(
                StudySession
            )
            .where(
                StudySession.subject_id
                == subject_id
            )
            .order_by(
                StudySession.session_date.desc(),
                StudySession.id.desc(),
            )
        ).all()

        attempt_items = [
            attempt_to_dict(
                attempt,
                include_quiz=False,
            )
            for attempt in attempts[:20]
        ]

        session_items = [
            study_session_to_dict(
                study_session,
                subject_name=subject.name,
            )
            for study_session in sessions[:20]
        ]

        total_minutes = sum(
            study_session.duration_minutes
            for study_session in sessions
        )

        completed_quizzes = [
            attempt
            for attempt in attempts
            if (
                attempt.status
                == "completed"
                and attempt.score_percentage
                is not None
            )
        ]

        quiz_average = None

        if completed_quizzes:
            quiz_average = round(
                sum(
                    attempt.score_percentage
                    for attempt
                    in completed_quizzes
                )
                / len(
                    completed_quizzes
                ),
                2,
            )

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            },
            "available_study_modes": sorted(
                SUPPORTED_STUDY_MODES
            ),
            "summary": {
                "study_session_count": (
                    len(sessions)
                ),
                "total_study_minutes": (
                    total_minutes
                ),
                "quiz_attempt_count": (
                    len(attempts)
                ),
                "completed_quiz_count": (
                    len(
                        completed_quizzes
                    )
                ),
                "quiz_average_percentage": (
                    quiz_average
                ),
            },
            "recent_attempts": (
                attempt_items
            ),
            "recent_study_sessions": (
                session_items
            ),
        }


def _build_subject_reviews(
    subject_id: int,
) -> dict:
    """
    Repasos de la asignatura.

    Prioriza lo vencido o más cercano.
    """

    now = datetime.now()

    with SessionLocal() as session:
        subject = _subject_exists(
            session,
            subject_id,
        )

        if subject is None:
            return {
                "ok": False,
                "error": (
                    "La asignatura no existe"
                ),
            }

        items = session.scalars(
            select(
                ReviewItem
            )
            .where(
                ReviewItem.subject_id
                == subject_id
            )
            .order_by(
                ReviewItem.next_review_at.asc(),
                ReviewItem.priority.desc(),
            )
        ).all()

        due_count = sum(
            1
            for item in items
            if item.next_review_at <= now
        )

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            },
            "count": len(items),
            "due_count": due_count,
            "reviews": [
                review_item_to_dict(
                    item
                )
                for item in items[:20]
            ],
        }


def _build_subject_assessments(
    subject_id: int,
) -> dict:
    """
    Evaluaciones de una asignatura.
    """

    with SessionLocal() as session:
        subject = _subject_exists(
            session,
            subject_id,
        )

        if subject is None:
            return {
                "ok": False,
                "error": (
                    "La asignatura no existe"
                ),
            }

        assessments = session.scalars(
            select(
                Assessment
            )
            .where(
                Assessment.subject_id
                == subject_id
            )
            .order_by(
                Assessment.assessment_date.is_(
                    None
                ),
                Assessment.assessment_date.asc(),
                Assessment.id.asc(),
            )
        ).all()

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            },
            "count": len(
                assessments
            ),
            "assessments": [
                assessment_to_dict(
                    assessment,
                    subject_name=subject.name,
                )
                for assessment
                in assessments
            ],
        }


def _build_subject_professor(
    subject_id: int,
) -> dict:
    """
    Profesores, preferencias y rúbricas
    asociadas a una asignatura.
    """

    with SessionLocal() as session:
        subject = _subject_exists(
            session,
            subject_id,
        )

        if subject is None:
            return {
                "ok": False,
                "error": (
                    "La asignatura no existe"
                ),
            }

        direct_professors = list(session.scalars(
            select(
                Professor
            )
            .where(
                Professor.subject_id
                == subject_id
            )
            .order_by(
                Professor.name.asc()
            )
        ).all())
        assigned_ids = list(session.scalars(
            select(ProfessorAssignment.professor_id).where(
                ProfessorAssignment.subject_id == subject_id
            )
        ))
        assigned_professors = list(session.scalars(
            select(Professor).where(Professor.id.in_(assigned_ids))
        )) if assigned_ids else []
        professors = sorted(
            {item.id: item for item in [*direct_professors, *assigned_professors]}.values(),
            key=lambda item: item.name.casefold(),
        )

        preferences = session.scalars(
            select(
                ProfessorPreference
            )
            .where(
                ProfessorPreference.subject_id
                == subject_id
            )
            .order_by(
                ProfessorPreference.importance.desc(),
                ProfessorPreference.confidence.desc(),
                ProfessorPreference.id.asc(),
            )
        ).all()

        rubrics = session.scalars(
            select(
                RubricCriterion
            )
            .where(
                RubricCriterion.subject_id
                == subject_id
            )
            .order_by(
                RubricCriterion.id.asc()
            )
        ).all()

        professor_names = {
            professor.id: professor.name
            for professor in professors
        }

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "academic_language": subject.academic_language,
                "academic_language_configured": subject.academic_language_configured,
            },
            "professors": [
                {
                    "id": professor.id,
                    "name": professor.name,
                    "public_profile_url": (
                        professor.public_profile_url
                    ),
                    "notes": professor.notes,
                }
                for professor in professors
            ],
            "preferences": [
                preference_to_dict(
                    preference,
                    professor_name=(
                        professor_names.get(
                            preference.professor_id
                        )
                    ),
                    subject_name=subject.name,
                )
                for preference
                in preferences
            ],
            "rubric_criteria": [
                rubric_to_dict(
                    criterion
                )
                for criterion
                in rubrics
            ],
        }


def _build_missions() -> dict:
    """
    Misiones actuales.
    """

    data = build_dashboard_data()

    if not data.get("ok"):
        return data

    return {
        "ok": True,
        "missions": data.get(
            "missions"
        ),
    }


def _build_next_boss() -> dict:
    """
    Próximo Boss Battle.
    """

    data = build_dashboard_data()

    if not data.get("ok"):
        return data

    return {
        "ok": True,
        "next_boss": data.get(
            "next_boss"
        ),
    }


def register_mcp_resources(
    mcp,
) -> None:
    """
    Registra Resources MCP de UniCore.

    Los Resources están agrupados por unidad
    de información útil, no por Tool antigua.
    """

    # -----------------------------
    # DIRECT RESOURCES
    # -----------------------------

    @mcp.resource(
        "unicore://profile"
    )
    def profile_resource() -> str:
        return _json(
            _build_profile()
        )

    @mcp.resource(
        "unicore://today"
    )
    def today_resource() -> str:
        return _json(
            _build_today()
        )

    @mcp.resource(
        "unicore://subjects"
    )
    def subjects_resource() -> str:
        return _json(
            _build_subjects()
        )

    @mcp.resource(
        "unicore://tasks"
    )
    def tasks_resource() -> str:
        return _json(
            _build_tasks()
        )

    @mcp.resource(
        "unicore://documents"
    )
    def documents_resource() -> str:
        return _json(
            _build_documents()
        )

    @mcp.resource(
        "unicore://missions"
    )
    def missions_resource() -> str:
        return _json(
            _build_missions()
        )

    @mcp.resource(
        "unicore://boss"
    )
    def boss_resource() -> str:
        return _json(
            _build_next_boss()
        )

    # -----------------------------
    # SUBJECT RESOURCE TEMPLATES
    # -----------------------------

    @mcp.resource(
        "unicore://subjects/{subject_id}"
    )
    def subject_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/dashboard"
        )
    )
    def subject_dashboard_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_dashboard(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/analytics"
        )
    )
    def subject_analytics_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_analytics(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/risk"
        )
    )
    def subject_risk_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_risk(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/grade"
        )
    )
    def subject_grade_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_grade(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/classes"
        )
    )
    def subject_classes_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_classes(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/study"
        )
    )
    def subject_study_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_study(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/reviews"
        )
    )
    def subject_reviews_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_reviews(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/tasks"
        )
    )
    def subject_tasks_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_tasks(
                subject_id=subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/assessments"
        )
    )
    def subject_assessments_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_assessments(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/professor"
        )
    )
    def subject_professor_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_subject_professor(
                subject_id
            )
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/documents"
        )
    )
    def subject_documents_resource(
        subject_id: int,
    ) -> str:
        return _json(
            _build_documents(
                subject_id=subject_id
            )
        )
