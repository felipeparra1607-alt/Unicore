from sqlalchemy import inspect, text

from src.database.connection import (
    engine,
)
from src.database.models import (
    Base,
)


def migrate_knowledge_map() -> None:
    """
    Crea las tablas e índices del Knowledge Map.
    """

    Base.metadata.create_all(
        bind=engine
    )

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_knowledge_concepts_subject_status "
                "ON knowledge_concepts "
                "(subject_id, status)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_knowledge_evidence_subject "
                "ON knowledge_evidence "
                "(subject_id)"
            )
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_knowledge_evidence_concept_observed "
                "ON knowledge_evidence "
                "(concept_id, observed_at)"
            )
        )

    inspector = inspect(
        engine
    )

    table_names = set(
        inspector.get_table_names()
    )

    required_tables = {
        "knowledge_concepts",
        "knowledge_evidence",
    }

    missing = (
        required_tables
        - table_names
    )

    if missing:
        print(
            "No se pudieron crear: "
            + ", ".join(
                sorted(missing)
            )
        )
        return

    print(
        "Migración de Knowledge Map completada."
    )


if __name__ == "__main__":
    migrate_knowledge_map()