from sqlalchemy import inspect, text

from src.database.connection import engine


def _add_column(connection, table: str, column: str, definition: str) -> None:
    columns = {item["name"] for item in inspect(connection).get_columns(table)}
    if column not in columns:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def migrate_material_classification(target_engine=None) -> None:
    """Añade clasificación documental sin reinterpretar datos existentes."""

    active_engine = target_engine or engine
    with active_engine.begin() as connection:
        _add_column(
            connection,
            "documents",
            "material_type",
            "VARCHAR(40) NOT NULL DEFAULT 'other'",
        )
        _add_column(
            connection,
            "documents",
            "curriculum_unit_id",
            "INTEGER REFERENCES curriculum_items(id) ON DELETE SET NULL",
        )
        connection.execute(text(
            "UPDATE documents SET material_type = 'other' "
            "WHERE material_type IS NULL OR TRIM(material_type) = ''"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_documents_material_type "
            "ON documents (material_type)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_documents_curriculum_unit_id "
            "ON documents (curriculum_unit_id)"
        ))


if __name__ == "__main__":
    migrate_material_classification()
