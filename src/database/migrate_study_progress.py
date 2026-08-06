from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_study_progress() -> None:
    """
    Crea las tablas necesarias para guardar
    intentos y respuestas de estudio.
    """

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_study_attempts_subject_status "
                "ON study_attempts "
                "(subject_id, status)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_study_attempts_completed_at "
                "ON study_attempts "
                "(completed_at)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_study_answers_attempt "
                "ON study_answers "
                "(attempt_id)"
            )
        )

    inspector = inspect(engine)

    required_tables = {
        "study_attempts",
        "study_answers",
    }

    existing_tables = set(
        inspector.get_table_names()
    )

    missing_tables = (
        required_tables - existing_tables
    )

    if missing_tables:
        print(
            "No se pudieron crear estas tablas: "
            + ", ".join(sorted(missing_tables))
        )
        return

    print(
        "Migración de progreso de estudio completada."
    )


if __name__ == "__main__":
    migrate_study_progress()