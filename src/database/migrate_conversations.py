from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models import Base


def migrate_conversations() -> None:
    """Crea las tablas e índices de memoria conversacional."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_conversations_updated_at "
                "ON conversations (updated_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_conversation_messages_conversation_created "
                "ON conversation_messages (conversation_id, created_at)"
            )
        )

    inspector = inspect(engine)
    required = {"conversations", "conversation_messages"}
    if not required.issubset(inspector.get_table_names()):
        raise RuntimeError("No se pudo preparar la memoria conversacional")


if __name__ == "__main__":
    migrate_conversations()
