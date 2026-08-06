from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    Subject,
)


ALLOWED_TASK_TYPES = {
    "assignment",
    "exam",
    "reading",
    "project",
    "presentation",
    "class_preparation",
    "administrative",
    "other",
}

ALLOWED_TASK_STATUSES = {
    "pending",
    "in_progress",
    "completed",
    "cancelled",
}


def clean_optional_text(
    value: str | None,
) -> str | None:
    """Limpia un texto opcional."""

    if value is None:
        return None

    cleaned = value.strip()

    return cleaned or None


def parse_optional_date(
    value: str | None,
) -> date | None:
    """Convierte una fecha YYYY-MM-DD."""

    if value is None or not value.strip():
        return None

    return date.fromisoformat(
        value.strip()
    )


def task_to_dict(
    task: AcademicTask,
    subject_name: str | None = None,
) -> dict[str, Any]:
    """Convierte una tarea en un diccionario."""

    today = date.today()

    days_until_due = (
        (task.due_date - today).days
        if task.due_date
        else None
    )

    is_overdue = (
        task.due_date is not None
        and task.due_date < today
        and task.status not in {
            "completed",
            "cancelled",
        }
    )

    remaining_minutes = None

    if task.estimated_minutes is not None:
        remaining_minutes = max(
            0,
            task.estimated_minutes
            - task.spent_minutes,
        )

    return {
        "id": task.id,
        "subject_id": task.subject_id,
        "subject_name": subject_name,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "due_date": (
            task.due_date.isoformat()
            if task.due_date
            else None
        ),
        "days_until_due": days_until_due,
        "is_overdue": is_overdue,
        "estimated_minutes": task.estimated_minutes,
        "spent_minutes": task.spent_minutes,
        "remaining_minutes": remaining_minutes,
        "progress_percentage": (
            task.progress_percentage
        ),
        "notes": task.notes,
        "completed_at": (
            task.completed_at.isoformat()
            if task.completed_at
            else None
        ),
        "created_at": (
            task.created_at.isoformat()
            if task.created_at
            else None
        ),
        "updated_at": (
            task.updated_at.isoformat()
            if task.updated_at
            else None
        ),
    }


def register_academic_task_tools(mcp) -> None:
    """Registra las herramientas de tareas académicas."""

    @mcp.tool()
    def create_academic_task(
        title: str,
        subject_id: int | None = None,
        description: str | None = None,
        task_type: str = "other",
        priority: int = 3,
        due_date: str | None = None,
        estimated_minutes: int | None = None,
        notes: str | None = None,
    ) -> dict:
        """Crea una tarea académica."""

        clean_title = title.strip()

        if not clean_title:
            return {
                "ok": False,
                "error": (
                    "El título no puede estar vacío"
                ),
            }

        clean_task_type = (
            task_type.strip().casefold()
        )

        if clean_task_type not in ALLOWED_TASK_TYPES:
            return {
                "ok": False,
                "error": (
                    "task_type no compatible. Usa "
                    "assignment, exam, reading, project, "
                    "presentation, class_preparation, "
                    "administrative u other"
                ),
            }

        if priority < 1 or priority > 5:
            return {
                "ok": False,
                "error": (
                    "priority debe estar entre 1 y 5"
                ),
            }

        if (
            estimated_minutes is not None
            and (
                estimated_minutes < 1
                or estimated_minutes > 100000
            )
        ):
            return {
                "ok": False,
                "error": (
                    "estimated_minutes debe estar "
                    "entre 1 y 100000"
                ),
            }

        try:
            parsed_due_date = parse_optional_date(
                due_date
            )
        except ValueError:
            return {
                "ok": False,
                "error": (
                    "due_date debe usar YYYY-MM-DD"
                ),
            }

        with SessionLocal() as session:
            subject = None

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

            task = AcademicTask(
                subject_id=subject_id,
                title=clean_title,
                description=clean_optional_text(
                    description
                ),
                task_type=clean_task_type,
                status="pending",
                priority=priority,
                due_date=parsed_due_date,
                estimated_minutes=estimated_minutes,
                spent_minutes=0,
                progress_percentage=0,
                notes=clean_optional_text(notes),
                updated_at=datetime.utcnow(),
            )

            session.add(task)
            session.commit()
            session.refresh(task)

            return {
                "ok": True,
                "task": task_to_dict(
                    task,
                    subject_name=(
                        subject.name
                        if subject
                        else None
                    ),
                ),
            }

    @mcp.tool()
    def list_academic_tasks(
        subject_id: int | None = None,
        status: str | None = None,
        task_type: str | None = None,
        overdue_only: bool = False,
        maximum_results: int = 100,
    ) -> dict:
        """Lista tareas académicas con filtros."""

        if maximum_results < 1 or maximum_results > 500:
            return {
                "ok": False,
                "error": (
                    "maximum_results debe estar "
                    "entre 1 y 500"
                ),
            }

        clean_status = None

        if status is not None and status.strip():
            clean_status = status.strip().casefold()

            if clean_status not in ALLOWED_TASK_STATUSES:
                return {
                    "ok": False,
                    "error": (
                        "status debe ser pending, "
                        "in_progress, completed o cancelled"
                    ),
                }

        clean_task_type = None

        if task_type is not None and task_type.strip():
            clean_task_type = (
                task_type.strip().casefold()
            )

            if clean_task_type not in ALLOWED_TASK_TYPES:
                return {
                    "ok": False,
                    "error": (
                        "task_type no es compatible"
                    ),
                }

        today = date.today()

        with SessionLocal() as session:
            statement = select(
                AcademicTask
            )

            if subject_id is not None:
                statement = statement.where(
                    AcademicTask.subject_id
                    == subject_id
                )

            if clean_status is not None:
                statement = statement.where(
                    AcademicTask.status
                    == clean_status
                )

            if clean_task_type is not None:
                statement = statement.where(
                    AcademicTask.task_type
                    == clean_task_type
                )

            if overdue_only:
                statement = statement.where(
                    AcademicTask.due_date < today,
                    AcademicTask.status.notin_(
                        ["completed", "cancelled"]
                    ),
                )

            statement = statement.order_by(
                AcademicTask.due_date.is_(None),
                AcademicTask.due_date.asc(),
                AcademicTask.priority.desc(),
                AcademicTask.id.asc(),
            ).limit(maximum_results)

            tasks = session.scalars(
                statement
            ).all()

            results = []

            for task in tasks:
                subject = (
                    session.get(
                        Subject,
                        task.subject_id,
                    )
                    if task.subject_id
                    else None
                )

                results.append(
                    task_to_dict(
                        task,
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
                "tasks": results,
            }

    @mcp.tool()
    def get_academic_task(
        task_id: int,
    ) -> dict:
        """Obtiene una tarea concreta."""

        with SessionLocal() as session:
            task = session.get(
                AcademicTask,
                task_id,
            )

            if task is None:
                return {
                    "ok": False,
                    "error": (
                        "La tarea no existe"
                    ),
                }

            subject = (
                session.get(
                    Subject,
                    task.subject_id,
                )
                if task.subject_id
                else None
            )

            return {
                "ok": True,
                "task": task_to_dict(
                    task,
                    subject_name=(
                        subject.name
                        if subject
                        else None
                    ),
                ),
            }

    @mcp.tool()
    def update_academic_task(
        task_id: int,
        title: str | None = None,
        description: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        due_date: str | None = None,
        estimated_minutes: int | None = None,
        spent_minutes: int | None = None,
        progress_percentage: int | None = None,
        notes: str | None = None,
    ) -> dict:
        """
        Actualiza una tarea académica.

        Para eliminar una fecha límite, usa due_date vacío.
        """

        with SessionLocal() as session:
            task = session.get(
                AcademicTask,
                task_id,
            )

            if task is None:
                return {
                    "ok": False,
                    "error": (
                        "La tarea no existe"
                    ),
                }

            if title is not None:
                clean_title = title.strip()

                if not clean_title:
                    return {
                        "ok": False,
                        "error": (
                            "El título no puede estar vacío"
                        ),
                    }

                task.title = clean_title

            if task_type is not None:
                clean_task_type = (
                    task_type.strip().casefold()
                )

                if (
                    clean_task_type
                    not in ALLOWED_TASK_TYPES
                ):
                    return {
                        "ok": False,
                        "error": (
                            "task_type no es compatible"
                        ),
                    }

                task.task_type = clean_task_type

            if status is not None:
                clean_status = (
                    status.strip().casefold()
                )

                if (
                    clean_status
                    not in ALLOWED_TASK_STATUSES
                ):
                    return {
                        "ok": False,
                        "error": (
                            "status debe ser pending, "
                            "in_progress, completed "
                            "o cancelled"
                        ),
                    }

                task.status = clean_status

                if clean_status == "completed":
                    task.progress_percentage = 100
                    task.completed_at = (
                        datetime.utcnow()
                    )
                elif task.status != "completed":
                    task.completed_at = None

            if priority is not None:
                if priority < 1 or priority > 5:
                    return {
                        "ok": False,
                        "error": (
                            "priority debe estar "
                            "entre 1 y 5"
                        ),
                    }

                task.priority = priority

            if due_date is not None:
                try:
                    task.due_date = (
                        parse_optional_date(
                            due_date
                        )
                    )
                except ValueError:
                    return {
                        "ok": False,
                        "error": (
                            "due_date debe usar "
                            "YYYY-MM-DD"
                        ),
                    }

            if estimated_minutes is not None:
                if (
                    estimated_minutes < 1
                    or estimated_minutes > 100000
                ):
                    return {
                        "ok": False,
                        "error": (
                            "estimated_minutes debe "
                            "estar entre 1 y 100000"
                        ),
                    }

                task.estimated_minutes = (
                    estimated_minutes
                )

            if spent_minutes is not None:
                if (
                    spent_minutes < 0
                    or spent_minutes > 100000
                ):
                    return {
                        "ok": False,
                        "error": (
                            "spent_minutes debe estar "
                            "entre 0 y 100000"
                        ),
                    }

                task.spent_minutes = spent_minutes

            if progress_percentage is not None:
                if (
                    progress_percentage < 0
                    or progress_percentage > 100
                ):
                    return {
                        "ok": False,
                        "error": (
                            "progress_percentage debe "
                            "estar entre 0 y 100"
                        ),
                    }

                task.progress_percentage = (
                    progress_percentage
                )

                if progress_percentage == 100:
                    task.status = "completed"
                    task.completed_at = (
                        datetime.utcnow()
                    )
                elif task.status == "completed":
                    task.status = "in_progress"
                    task.completed_at = None

            if description is not None:
                task.description = clean_optional_text(
                    description
                )

            if notes is not None:
                task.notes = clean_optional_text(
                    notes
                )

            task.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(task)

            subject = (
                session.get(
                    Subject,
                    task.subject_id,
                )
                if task.subject_id
                else None
            )

            return {
                "ok": True,
                "task": task_to_dict(
                    task,
                    subject_name=(
                        subject.name
                        if subject
                        else None
                    ),
                ),
            }

    @mcp.tool()
    def complete_academic_task(
        task_id: int,
        spent_minutes: int | None = None,
        notes: str | None = None,
    ) -> dict:
        """Marca una tarea como completada."""

        if (
            spent_minutes is not None
            and (
                spent_minutes < 0
                or spent_minutes > 100000
            )
        ):
            return {
                "ok": False,
                "error": (
                    "spent_minutes debe estar "
                    "entre 0 y 100000"
                ),
            }

        with SessionLocal() as session:
            task = session.get(
                AcademicTask,
                task_id,
            )

            if task is None:
                return {
                    "ok": False,
                    "error": (
                        "La tarea no existe"
                    ),
                }

            task.status = "completed"
            task.progress_percentage = 100
            task.completed_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()

            if spent_minutes is not None:
                task.spent_minutes = spent_minutes

            if notes is not None:
                task.notes = clean_optional_text(
                    notes
                )

            session.commit()
            session.refresh(task)

            subject = (
                session.get(
                    Subject,
                    task.subject_id,
                )
                if task.subject_id
                else None
            )

            return {
                "ok": True,
                "task": task_to_dict(
                    task,
                    subject_name=(
                        subject.name
                        if subject
                        else None
                    ),
                ),
            }

    @mcp.tool()
    def delete_academic_task(
        task_id: int,
    ) -> dict:
        """Elimina una tarea académica."""

        with SessionLocal() as session:
            task = session.get(
                AcademicTask,
                task_id,
            )

            if task is None:
                return {
                    "ok": False,
                    "error": (
                        "La tarea no existe"
                    ),
                }

            deleted_title = task.title

            session.delete(task)
            session.commit()

            return {
                "ok": True,
                "deleted_task_id": task_id,
                "deleted_title": deleted_title,
            }