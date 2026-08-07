from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_professor_rubrics() -> None:
    """Crea tablas de preferencias del profesor y rúbricas."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_professor_preferences_professor "
                "ON professor_preferences "
                "(professor_id)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_professor_preferences_subject "
                "ON professor_preferences "
                "(subject_id)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_rubric_criteria_assessment "
                "ON rubric_criteria "
                "(assessment_id)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_rubric_criteria_subject "
                "ON rubric_criteria "
                "(subject_id)"
            )
        )

    inspector = inspect(engine)

    required_tables = {
        "professor_preferences",
        "rubric_criteria",
    }

    existing_tables = set(
        inspector.get_table_names()
    )

    missing = required_tables - existing_tables

    if missing:
        print(
            "No se pudieron crear: "
            + ", ".join(sorted(missing))
        )
        return

    print(
        "Migración de preferencias y rúbricas completada."
    )


if __name__ == "__main__":
    migrate_professor_rubrics()