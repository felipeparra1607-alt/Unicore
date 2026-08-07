from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_boss_battles() -> None:
    """Crea la tabla e índices de Boss Battles."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_boss_battles_assessment "
                "ON boss_battles "
                "(assessment_id)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_boss_battles_subject_status "
                "ON boss_battles "
                "(subject_id, status)"
            )
        )

    inspector = inspect(engine)

    if (
        "boss_battles"
        not in inspector.get_table_names()
    ):
        print(
            "No se pudo crear la tabla boss_battles."
        )
        return

    print(
        "Migración de Boss Battles completada."
    )


if __name__ == "__main__":
    migrate_boss_battles()