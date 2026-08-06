from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_review_items() -> None:
    """Crea la tabla e índices del repaso inteligente."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_review_items_subject_status "
                "ON review_items "
                "(subject_id, status)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_review_items_next_review "
                "ON review_items "
                "(next_review_at)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_review_items_source_answer "
                "ON review_items "
                "(source_answer_id)"
            )
        )

    inspector = inspect(engine)

    if "review_items" not in inspector.get_table_names():
        print(
            "No se pudo crear la tabla review_items."
        )
        return

    print(
        "Migración de repaso inteligente completada."
    )


if __name__ == "__main__":
    migrate_review_items()