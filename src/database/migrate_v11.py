from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def _add_column(connection, table: str, column: str, definition: str) -> None:
    columns = {item["name"] for item in inspect(connection).get_columns(table)}
    if column not in columns:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def migrate_v11() -> None:
    """Añade de forma aditiva la persistencia de Academic Memory V1.1."""

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        _add_column(connection, "subjects", "academic_language", "VARCHAR(30) NOT NULL DEFAULT 'Spanish'")
        _add_column(connection, "subjects", "academic_language_configured", "BOOLEAN NOT NULL DEFAULT 0")
        connection.execute(text(
            "UPDATE subjects SET academic_language_configured = 1 "
            "WHERE academic_language = 'English' AND academic_language_configured = 0"
        ))
        _add_column(connection, "documents", "academic_year", "VARCHAR(20)")
        _add_column(connection, "documents", "semester", "VARCHAR(40)")
        _add_column(connection, "documents", "professor_id", "INTEGER REFERENCES professors(id)")
        _add_column(connection, "documents", "curriculum_processed_at", "DATETIME")
        _add_column(connection, "documents", "processing_status", "VARCHAR(30) NOT NULL DEFAULT 'ready'")
        _add_column(connection, "documents", "processing_stage", "VARCHAR(100)")
        _add_column(connection, "documents", "processing_error", "TEXT")
        _add_column(connection, "knowledge_concepts", "global_concept_id", "INTEGER REFERENCES global_concepts(id)")
        _add_column(connection, "review_items", "leitner_box", "INTEGER NOT NULL DEFAULT 1")
        _add_column(connection, "review_items", "cognitive_level", "VARCHAR(30) NOT NULL DEFAULT 'mixed'")
        _add_column(connection, "review_items", "concept_name", "VARCHAR(250)")
        _add_column(connection, "review_items", "last_rating", "VARCHAR(30)")
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_token_usage_created_at ON token_usage (created_at)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_student_model_dimension_date "
            "ON student_model_evidence (dimension, observed_at)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_concepts_global_concept_id "
            "ON knowledge_concepts (global_concept_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_curriculum_subject_parent "
            "ON curriculum_items (subject_id, parent_id, position)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_explanation_cache_lookup "
            "ON explanation_cache (subject_id, document_id, curriculum_item_id, topic_key, difficulty)"
        ))


if __name__ == "__main__":
    migrate_v11()
