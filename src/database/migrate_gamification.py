from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_gamification() -> None:
    """Crea las tablas del sistema de gamificación."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_gamification_events_source_key "
                "ON gamification_events "
                "(source_key)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_gamification_events_subject "
                "ON gamification_events "
                "(subject_id)"
            )
        )

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_achievement_unlocks_key_subject "
                "ON achievement_unlocks "
                "(achievement_key, subject_id)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_daily_missions_date "
                "ON daily_missions "
                "(mission_date)"
            )
        )

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ux_daily_missions_date_source "
                "ON daily_missions "
                "(mission_date, source_key)"
            )
        )

    inspector = inspect(engine)

    required = {
        "gamification_events",
        "achievement_unlocks",
        "daily_missions",
    }

    existing = set(
        inspector.get_table_names()
    )

    missing = required - existing

    if missing:
        print(
            "No se pudieron crear: "
            + ", ".join(sorted(missing))
        )
        return

    print(
        "Migración de gamificación completada."
    )


if __name__ == "__main__":
    migrate_gamification()