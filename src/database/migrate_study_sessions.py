from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_study_sessions() -> None:
    """Crea la tabla e índices de sesiones de estudio."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_study_sessions_subject_date "
                "ON study_sessions "
                "(subject_id, session_date)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_study_sessions_activity "
                "ON study_sessions "
                "(activity_type)"
            )
        )

    inspector = inspect(engine)

    if "study_sessions" not in inspector.get_table_names():
        print(
            "No se pudo crear la tabla study_sessions."
        )
        return

    print(
        "Migración de sesiones de estudio completada."
    )


if __name__ == "__main__":
    migrate_study_sessions()