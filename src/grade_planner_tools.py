from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    Assessment,
    GradeGoal,
    Subject,
)


def register_grade_planner_tools(mcp) -> None:

    @mcp.tool()
    def get_subject_grade_status(
        subject_id: int,
    ) -> dict:
        """
        Calcula la situación académica de una asignatura.

        Diferencia entre:
        - nota obtenida sobre lo ya evaluado;
        - puntos acumulados sobre la nota final;
        - peso todavía pendiente.
        """

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

            assessments = session.scalars(
                select(Assessment)
                .where(
                    Assessment.subject_id
                    == subject_id,
                    Assessment.status
                    != "cancelled",
                )
                .order_by(
                    Assessment.assessment_date.asc(),
                    Assessment.id.asc(),
                )
            ).all()

            completed = [
                assessment
                for assessment in assessments
                if (
                    assessment.status
                    == "completed"
                    and assessment.obtained_grade
                    is not None
                )
            ]

            pending = [
                assessment
                for assessment in assessments
                if assessment.status == "pending"
            ]

            total_defined_weight = sum(
                assessment.weight_percentage
                for assessment in assessments
            )

            evaluated_weight = sum(
                assessment.weight_percentage
                for assessment in completed
            )

            pending_defined_weight = sum(
                assessment.weight_percentage
                for assessment in pending
            )

            accumulated_final_percentage = sum(
                (
                    assessment.obtained_grade
                    / assessment.maximum_grade
                )
                * assessment.weight_percentage
                for assessment in completed
            )

            grade_on_evaluated_work = (
                (
                    accumulated_final_percentage
                    / evaluated_weight
                )
                * 10
                if evaluated_weight > 0
                else None
            )

            goal = session.scalar(
                select(GradeGoal).where(
                    GradeGoal.subject_id
                    == subject_id
                )
            )

            target_grade = (
                goal.target_grade
                if goal
                else None
            )

            maximum_grade = (
                goal.maximum_grade
                if goal
                else 10.0
            )

            required_average_on_remaining = None
            target_status = None

            if goal is not None:
                target_percentage = (
                    target_grade
                    / maximum_grade
                    * 100
                )

                remaining_weight = (
                    100 - evaluated_weight
                )

                required_points = (
                    target_percentage
                    - accumulated_final_percentage
                )

                if required_points <= 0:
                    required_average_on_remaining = 0.0
                    target_status = (
                        "already_secured"
                    )

                elif remaining_weight <= 0:
                    required_average_on_remaining = None
                    target_status = (
                        "target_not_reached"
                    )

                else:
                    required_fraction = (
                        required_points
                        / remaining_weight
                    )

                    required_average_on_remaining = (
                        round(
                            required_fraction
                            * maximum_grade,
                            2,
                        )
                    )

                    if (
                        required_average_on_remaining
                        > maximum_grade
                    ):
                        target_status = "impossible"
                    else:
                        target_status = "possible"

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "assessment_summary": {
                    "defined_assessment_count": len(
                        assessments
                    ),
                    "completed_count": len(
                        completed
                    ),
                    "pending_count": len(
                        pending
                    ),
                    "total_defined_weight_percentage": (
                        round(
                            total_defined_weight,
                            4,
                        )
                    ),
                    "evaluated_weight_percentage": (
                        round(
                            evaluated_weight,
                            4,
                        )
                    ),
                    "pending_defined_weight_percentage": (
                        round(
                            pending_defined_weight,
                            4,
                        )
                    ),
                    "undefined_weight_percentage": (
                        round(
                            max(
                                0,
                                100
                                - total_defined_weight,
                            ),
                            4,
                        )
                    ),
                },
                "current_performance": {
                    "grade_on_evaluated_work_out_of_10": (
                        round(
                            grade_on_evaluated_work,
                            2,
                        )
                        if grade_on_evaluated_work
                        is not None
                        else None
                    ),
                    "accumulated_final_percentage": (
                        round(
                            accumulated_final_percentage,
                            4,
                        )
                    ),
                    "equivalent_accumulated_grade_out_of_10": (
                        round(
                            accumulated_final_percentage
                            / 10,
                            2,
                        )
                    ),
                },
                "goal": (
                    {
                        "target_grade": (
                            target_grade
                        ),
                        "maximum_grade": (
                            maximum_grade
                        ),
                        "status": target_status,
                        "required_average_on_remaining": (
                            required_average_on_remaining
                        ),
                    }
                    if goal
                    else None
                ),
            }

    @mcp.tool()
    def simulate_assessment_grade(
        subject_id: int,
        assessment_id: int,
        hypothetical_grade: float,
    ) -> dict:
        """
        Simula una nota sin guardarla en la base de datos.
        """

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

            if (
                hypothetical_grade < 0
                or hypothetical_grade
                > assessment.maximum_grade
            ):
                return {
                    "ok": False,
                    "error": (
                        "La nota simulada debe estar entre "
                        f"0 y {assessment.maximum_grade}"
                    ),
                }

            completed = session.scalars(
                select(Assessment).where(
                    Assessment.subject_id
                    == subject_id,
                    Assessment.status
                    == "completed",
                    Assessment.obtained_grade
                    .is_not(None),
                    Assessment.id
                    != assessment_id,
                )
            ).all()

            accumulated_percentage = sum(
                (
                    item.obtained_grade
                    / item.maximum_grade
                )
                * item.weight_percentage
                for item in completed
            )

            simulated_contribution = (
                hypothetical_grade
                / assessment.maximum_grade
            ) * assessment.weight_percentage

            simulated_total = (
                accumulated_percentage
                + simulated_contribution
            )

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "assessment": {
                    "id": assessment.id,
                    "title": assessment.title,
                    "weight_percentage": (
                        assessment.weight_percentage
                    ),
                    "maximum_grade": (
                        assessment.maximum_grade
                    ),
                },
                "simulation": {
                    "hypothetical_grade": (
                        hypothetical_grade
                    ),
                    "simulated_contribution_percentage": (
                        round(
                            simulated_contribution,
                            4,
                        )
                    ),
                    "accumulated_final_percentage_after": (
                        round(
                            simulated_total,
                            4,
                        )
                    ),
                    "equivalent_accumulated_grade_out_of_10": (
                        round(
                            simulated_total / 10,
                            2,
                        )
                    ),
                },
                "saved": False,
            }