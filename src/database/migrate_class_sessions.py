from sqlalchemy import inspect, text

from src.database.connection import engine


NEW_COLUMNS = {
    "start_time": "VARCHAR(5)",
    "end_time": "VARCHAR(5)",
    "session_type": "VARCHAR(50)",
    "location": "VARCHAR(250)",
    "attended": "BOOLEAN NOT NULL DEFAULT 1",
    "professor_id": (
        "INTEGER REFERENCES professors(id)"
    ),
    "source_document_id": (
        "INTEGER REFERENCES documents(id)"
    ),
    "topics": "TEXT",
    "notes": "TEXT",
    "doubts": "TEXT",
    "tasks": "TEXT",
    "updated_at": "DATETIME",
}


def migrate_class_sessions() -> None:
    """Añade las nuevas columnas sin borrar datos existentes."""

    inspector = inspect(engine)

    if "class_sessions" not in inspector.get_table_names():
        print(
            "La tabla class_sessions no existe. "
            "Ejecuta primero la inicialización de la base."
        )
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(
            "class_sessions"
        )
    }

    with engine.begin() as connection:
        for column_name, column_definition in (
            NEW_COLUMNS.items()
        ):
            if column_name in existing_columns:
                print(
                    f"Ya existe: {column_name}"
                )
                continue

            connection.execute(
                text(
                    "ALTER TABLE class_sessions "
                    f"ADD COLUMN {column_name} "
                    f"{column_definition}"
                )
            )

            print(
                f"Añadida: {column_name}"
            )

        connection.execute(
            text(
                "UPDATE class_sessions "
                "SET updated_at = created_at "
                "WHERE updated_at IS NULL"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_class_sessions_subject_date "
                "ON class_sessions "
                "(subject_id, class_date)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_class_sessions_professor "
                "ON class_sessions "
                "(professor_id)"
            )
        )

    print(
        "Migración de sesiones completada."
    )


if __name__ == "__main__":
    migrate_class_sessions()