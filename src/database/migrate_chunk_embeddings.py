from sqlalchemy import text

from src.database.connection import engine


REQUIRED_COLUMNS = {
    "chunking_strategy": (
        "TEXT NOT NULL DEFAULT 'hybrid_semantic'"
    ),
    "embedding_model": "TEXT",
    "embedding_json": "TEXT",
}


def get_existing_columns(connection) -> set[str]:
    """Devuelve las columnas actuales de document_chunks."""

    result = connection.execute(
        text("PRAGMA table_info(document_chunks)")
    )

    return {
        row[1]
        for row in result
    }


def run_migration() -> None:
    """Añade las columnas que falten sin eliminar datos."""

    with engine.begin() as connection:
        existing_columns = get_existing_columns(connection)

        if not existing_columns:
            raise RuntimeError(
                "La tabla document_chunks no existe. "
                "Ejecuta primero: python -m src.database.init_db"
            )

        added_columns: list[str] = []

        for column_name, column_definition in REQUIRED_COLUMNS.items():
            if column_name in existing_columns:
                continue

            connection.execute(
                text(
                    f"ALTER TABLE document_chunks "
                    f"ADD COLUMN {column_name} "
                    f"{column_definition}"
                )
            )

            added_columns.append(column_name)

    if added_columns:
        print(
            "Columnas añadidas correctamente: "
            + ", ".join(added_columns)
        )
    else:
        print(
            "La migración ya estaba aplicada. "
            "No fue necesario modificar la base de datos."
        )


if __name__ == "__main__":
    run_migration()