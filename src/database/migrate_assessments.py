from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_assessments() -> None:
    """Crea tablas e índices de evaluaciones y objetivos."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_assessments_subject_status "
                "ON assessments "
                "(subject_id, status)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_assessments_subject_date "
                "ON assessments "
                "(subject_id, assessment_date)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_grade_goals_subject "
                "ON grade_goals "
                "(subject_id)"
            )
        )

    inspector = inspect(engine)

    required_tables = {
        "assessments",
        "grade_goals",
    }

    existing_tables = set(
        inspector.get_table_names()
    )

    missing_tables = (
        required_tables - existing_tables
    )

    if missing_tables:
        print(
            "No se pudieron crear: "
            + ", ".join(
                sorted(missing_tables)
            )
        )
        return

    print(
        "Migración de evaluaciones completada."
    )


if __name__ == "__main__":
    migrate_assessments()