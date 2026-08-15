from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from src.database.connection import engine


def migrate_curriculum_dirty(target_engine: Engine | None = None) -> None:
    """Añade el indicador estructural sin reconstruir ni alterar datos académicos."""

    active_engine = target_engine or engine
    columns = {column["name"] for column in inspect(active_engine).get_columns("subjects")}
    with active_engine.begin() as connection:
        if "curriculum_dirty" not in columns:
            connection.execute(text(
                "ALTER TABLE subjects ADD COLUMN curriculum_dirty BOOLEAN NOT NULL DEFAULT 0"
            ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_subjects_curriculum_dirty "
            "ON subjects (curriculum_dirty)"
        ))


if __name__ == "__main__":
    migrate_curriculum_dirty()
