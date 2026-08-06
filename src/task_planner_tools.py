from datetime import date
from typing import Any

from sqlalchemy import select

from src.academic_task_tools import task_to_dict
from src.database.connection import SessionLocal
from src.database.models import (
    AcademicTask,
    Subject,
)


def calculate_task_urgency(
    task: AcademicTask,
    today: date,
) -> dict[str, Any]:
    """Calcula la urgencia y la puntuación de una tarea."""

    if task.due_date is None:
        days_until_due = None
        urgency_points = 0
    else:
        days_until_due = (
            task.due_date - today
        ).days

        if days_until_due < 0:
            urgency_points = 100
        elif days_until_due == 0:
            urgency_points = 80
        elif days_until_due == 1:
            urgency_points = 60
        elif days_until_due <= 3:
            urgency_points = 40
        elif days_until_due <= 7:
            urgency_points = 20
        else:
            urgency_points = 5

    priority_points = task.priority * 10

    progress_points = round(
        (100 - task.progress_percentage)
        * 0.1
    )

    remaining_minutes = (
        max(
            0,
            task.estimated_minutes
            - task.spent_minutes,
        )
        if task.estimated_minutes is not None
        else None
    )

    score = (
        urgency_points
        + priority_points
        + progress_points
    )

    return {
        "days_until_due": days_until_due,
        "urgency_points": urgency_points,
        "priority_points": priority_points,
        "progress_points": progress_points,
        "planning_score": score,
        "remaining_minutes": remaining_minutes,
    }


def register_task_planner_tools(mcp) -> None:
    """Registra el planificador de tareas."""

    @mcp.tool()
    def get_task_priority_plan(
        subject_id: int | None = None,
        maximum_results: int = 20,
    ) -> dict:
        """
        Ordena las tareas pendientes según urgencia
        e importancia.
        """

        if maximum_results < 1 or maximum_results > 100:
            return {
                "ok": False,
                "error": (
                    "maximum_results debe estar "
                    "entre 1 y 100"
                ),
            }

        today = date.today()

        with SessionLocal() as session:
            statement = select(
                AcademicTask
            ).where(
                AcademicTask.status.notin_(
                    ["completed", "cancelled"]
                )
            )

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

                statement = statement.where(
                    AcademicTask.subject_id
                    == subject_id
                )
            else:
                subject = None

            tasks = session.scalars(
                statement
            ).all()

            ranked_tasks = []

            for task in tasks:
                task_subject = (
                    session.get(
                        Subject,
                        task.subject_id,
                    )
                    if task.subject_id
                    else None
                )

                calculation = calculate_task_urgency(
                    task,
                    today,
                )

                ranked_tasks.append({
                    "task": task_to_dict(
                        task,
                        subject_name=(
                            task_subject.name
                            if task_subject
                            else None
                        ),
                    ),
                    "priority_calculation": (
                        calculation
                    ),
                })

            ranked_tasks.sort(
                key=lambda item: (
                    -item[
                        "priority_calculation"
                    ]["planning_score"],
                    (
                        item["task"]["due_date"]
                        is None
                    ),
                    item["task"]["due_date"] or "",
                    item["task"]["id"],
                )
            )

            selected_tasks = ranked_tasks[
                :maximum_results
            ]

            return {
                "ok": True,
                "generated_for_date": (
                    today.isoformat()
                ),
                "subject": (
                    {
                        "id": subject.id,
                        "name": subject.name,
                    }
                    if subject
                    else None
                ),
                "pending_task_count": len(
                    ranked_tasks
                ),
                "result_count": len(
                    selected_tasks
                ),
                "tasks": selected_tasks,
            }

    @mcp.tool()
    def get_today_task_plan(
        available_minutes: int,
        subject_id: int | None = None,
        maximum_tasks: int = 10,
    ) -> dict:
        """
        Construye un plan para hoy con el tiempo disponible.

        Divide tareas grandes en bloques parciales.
        """

        if available_minutes < 5 or available_minutes > 1440:
            return {
                "ok": False,
                "error": (
                    "available_minutes debe estar "
                    "entre 5 y 1440"
                ),
            }

        if maximum_tasks < 1 or maximum_tasks > 50:
            return {
                "ok": False,
                "error": (
                    "maximum_tasks debe estar "
                    "entre 1 y 50"
                ),
            }

        today = date.today()

        with SessionLocal() as session:
            statement = select(
                AcademicTask
            ).where(
                AcademicTask.status.notin_(
                    ["completed", "cancelled"]
                )
            )

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

                statement = statement.where(
                    AcademicTask.subject_id
                    == subject_id
                )
            else:
                subject = None

            tasks = session.scalars(
                statement
            ).all()

            ranked_tasks = []

            for task in tasks:
                calculation = calculate_task_urgency(
                    task,
                    today,
                )

                ranked_tasks.append(
                    (
                        task,
                        calculation,
                    )
                )

            ranked_tasks.sort(
                key=lambda item: (
                    -item[1]["planning_score"],
                    item[0].due_date is None,
                    item[0].due_date or date.max,
                    item[0].id,
                )
            )

            remaining_minutes = available_minutes
            plan_steps = []

            for task, calculation in ranked_tasks:
                if (
                    remaining_minutes < 5
                    or len(plan_steps)
                    >= maximum_tasks
                ):
                    break

                task_subject = (
                    session.get(
                        Subject,
                        task.subject_id,
                    )
                    if task.subject_id
                    else None
                )

                remaining_task_minutes = (
                    calculation[
                        "remaining_minutes"
                    ]
                )

                if remaining_task_minutes is None:
                    suggested_minutes = min(
                        remaining_minutes,
                        30,
                    )
                else:
                    suggested_minutes = min(
                        remaining_minutes,
                        max(
                            5,
                            remaining_task_minutes,
                        ),
                    )

                plan_steps.append({
                    "order": len(plan_steps) + 1,
                    "task_id": task.id,
                    "title": task.title,
                    "subject_id": task.subject_id,
                    "subject_name": (
                        task_subject.name
                        if task_subject
                        else None
                    ),
                    "task_type": task.task_type,
                    "priority": task.priority,
                    "due_date": (
                        task.due_date.isoformat()
                        if task.due_date
                        else None
                    ),
                    "days_until_due": (
                        calculation[
                            "days_until_due"
                        ]
                    ),
                    "progress_percentage": (
                        task.progress_percentage
                    ),
                    "planning_score": (
                        calculation[
                            "planning_score"
                        ]
                    ),
                    "suggested_minutes": (
                        suggested_minutes
                    ),
                    "completes_estimated_work": (
                        remaining_task_minutes
                        is not None
                        and suggested_minutes
                        >= remaining_task_minutes
                    ),
                })

                remaining_minutes -= (
                    suggested_minutes
                )

            return {
                "ok": True,
                "generated_for_date": (
                    today.isoformat()
                ),
                "subject": (
                    {
                        "id": subject.id,
                        "name": subject.name,
                    }
                    if subject
                    else None
                ),
                "available_minutes": (
                    available_minutes
                ),
                "planned_minutes": sum(
                    step["suggested_minutes"]
                    for step in plan_steps
                ),
                "unallocated_minutes": (
                    remaining_minutes
                ),
                "pending_task_count": len(
                    ranked_tasks
                ),
                "selected_task_count": len(
                    plan_steps
                ),
                "steps": plan_steps,
                "provider_called": False,
                "estimated_cost_usd": 0,
            }