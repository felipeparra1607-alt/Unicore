from mcp.server import MCPServer
from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import Subject


mcp = MCPServer("UniCore")


@mcp.tool()
def health_check() -> str:
    """Comprueba que el servidor UniCore está funcionando."""
    return "UniCore MCP funcionando correctamente"


@mcp.tool()
def create_subject(
    name: str,
    academic_year: str | None = None,
    description: str | None = None,
) -> dict:
    """Crea una nueva asignatura en UniCore."""

    with SessionLocal() as session:
        existing_subject = session.scalar(
            select(Subject).where(Subject.name == name)
        )

        if existing_subject:
            return {
                "ok": False,
                "error": "La asignatura ya existe",
                "subject_id": existing_subject.id,
            }

        subject = Subject(
            name=name,
            academic_year=academic_year,
            description=description,
        )

        session.add(subject)
        session.commit()
        session.refresh(subject)

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "academic_year": subject.academic_year,
                "description": subject.description,
            },
        }


@mcp.tool()
def list_subjects() -> list[dict]:
    """Devuelve todas las asignaturas guardadas en UniCore."""

    with SessionLocal() as session:
        subjects = session.scalars(
            select(Subject).order_by(Subject.name)
        ).all()

        return [
            {
                "id": subject.id,
                "name": subject.name,
                "academic_year": subject.academic_year,
                "description": subject.description,
            }
            for subject in subjects
        ]