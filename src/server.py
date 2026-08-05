from mcp.server import MCPServer
from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import Subject


mcp = MCPServer("UniCore")


def subject_to_dict(subject: Subject) -> dict:
    """Convierte una asignatura de la base de datos en un diccionario."""
    return {
        "id": subject.id,
        "name": subject.name,
        "academic_year": subject.academic_year,
        "description": subject.description,
    }


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

    clean_name = name.strip()

    if not clean_name:
        return {
            "ok": False,
            "error": "El nombre de la asignatura no puede estar vacío",
        }

    with SessionLocal() as session:
        existing_subject = session.scalar(
            select(Subject).where(Subject.name == clean_name)
        )

        if existing_subject:
            return {
                "ok": False,
                "error": "La asignatura ya existe",
                "subject_id": existing_subject.id,
            }

        subject = Subject(
            name=clean_name,
            academic_year=academic_year,
            description=description,
        )

        session.add(subject)
        session.commit()
        session.refresh(subject)

        return {
            "ok": True,
            "subject": subject_to_dict(subject),
        }


@mcp.tool()
def list_subjects() -> list[dict]:
    """Devuelve todas las asignaturas guardadas en UniCore."""

    with SessionLocal() as session:
        subjects = session.scalars(
            select(Subject).order_by(Subject.name)
        ).all()

        return [subject_to_dict(subject) for subject in subjects]


@mcp.tool()
def get_subject(subject_id: int) -> dict:
    """Devuelve una asignatura concreta por su ID."""

    with SessionLocal() as session:
        subject = session.get(Subject, subject_id)

        if subject is None:
            return {
                "ok": False,
                "error": "Asignatura no encontrada",
            }

        return {
            "ok": True,
            "subject": subject_to_dict(subject),
        }


@mcp.tool()
def update_subject(
    subject_id: int,
    name: str | None = None,
    academic_year: str | None = None,
    description: str | None = None,
) -> dict:
    """Actualiza los datos de una asignatura existente."""

    with SessionLocal() as session:
        subject = session.get(Subject, subject_id)

        if subject is None:
            return {
                "ok": False,
                "error": "Asignatura no encontrada",
            }

        if name is not None:
            clean_name = name.strip()

            if not clean_name:
                return {
                    "ok": False,
                    "error": "El nombre de la asignatura no puede estar vacío",
                }

            duplicate = session.scalar(
                select(Subject).where(
                    Subject.name == clean_name,
                    Subject.id != subject_id,
                )
            )

            if duplicate:
                return {
                    "ok": False,
                    "error": "Ya existe otra asignatura con ese nombre",
                }

            subject.name = clean_name

        if academic_year is not None:
            subject.academic_year = academic_year

        if description is not None:
            subject.description = description

        session.commit()
        session.refresh(subject)

        return {
            "ok": True,
            "subject": subject_to_dict(subject),
        }


@mcp.tool()
def delete_subject(subject_id: int) -> dict:
    """Elimina una asignatura por su ID."""

    with SessionLocal() as session:
        subject = session.get(Subject, subject_id)

        if subject is None:
            return {
                "ok": False,
                "error": "Asignatura no encontrada",
            }

        subject_name = subject.name

        session.delete(subject)
        session.commit()

        return {
            "ok": True,
            "message": "Asignatura eliminada correctamente",
            "subject": {
                "id": subject_id,
                "name": subject_name,
            },
        }