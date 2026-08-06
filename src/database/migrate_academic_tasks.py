from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_academic_tasks() -> None:
    """Crea la tabla e índices de tareas académicas."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_academic_tasks_subject_status "
                "ON academic_tasks "
                "(subject_id, status)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_academic_tasks_due_date "
                "ON academic_tasks "
                "(due_date)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_academic_tasks_priority "
                "ON academic_tasks "
                "(priority)"
            )
        )

    inspector = inspect(engine)

    if "academic_tasks" not in inspector.get_table_names():
        print(
            "No se pudo crear la tabla academic_tasks."
        )
        return

    print(
        "Migración de tareas académicas completada."
    )


if __name__ == "__main__":
    migrate_academic_tasks()