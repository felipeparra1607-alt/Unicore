from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_study_analysis_v1() -> None:
    """Crea de forma aditiva el cache de análisis por Topic/Subtopic."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if "study_topic_analyses" not in tables:
            # Base.metadata.create_all normalmente habrá creado la tabla. Este
            # guard evita continuar silenciosamente si el modelo no se cargó.
            raise RuntimeError("No se pudo crear study_topic_analyses")

        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_study_topic_analysis_subject_item "
            "ON study_topic_analyses (subject_id, curriculum_item_id)"
        ))


if __name__ == "__main__":
    migrate_study_analysis_v1()