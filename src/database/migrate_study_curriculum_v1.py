from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def _add_column(connection, table: str, column: str, definition: str) -> None:
    columns = {item["name"] for item in inspect(connection).get_columns(table)}
    if column not in columns:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def migrate_study_curriculum_v1() -> None:
    """Añade de forma aditiva la estructura Topic/Subtopic para prioridad y flashcards."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        _add_column(
            connection,
            "curriculum_items",
            "importance_mode",
            "VARCHAR(20) NOT NULL DEFAULT 'auto'",
        )
        _add_column(
            connection,
            "curriculum_items",
            "manual_importance",
            "INTEGER",
        )
        _add_column(
            connection,
            "review_items",
            "curriculum_item_id",
            "INTEGER REFERENCES curriculum_items(id) ON DELETE SET NULL",
        )
        _add_column(
            connection,
            "flashcard_drafts",
            "curriculum_item_id",
            "INTEGER REFERENCES curriculum_items(id) ON DELETE SET NULL",
        )

        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_review_items_curriculum_item_id "
            "ON review_items (curriculum_item_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flashcard_drafts_curriculum_item_id "
            "ON flashcard_drafts (curriculum_item_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_curriculum_importance "
            "ON curriculum_items (subject_id, item_type, importance_mode, manual_importance)"
        ))


if __name__ == "__main__":
    migrate_study_curriculum_v1()