from mcp.server import MCPServer
from sqlalchemy import func, select

from src.database.connection import SessionLocal
from src.database.models import Professor, Subject


mcp = MCPServer("UniCore")


def subject_to_dict(subject: Subject) -> dict:
    """Convierte una asignatura de la base de datos en un diccionario."""
    return {
        "id": subject.id,
        "name": subject.name,
        "academic_year": subject.academic_year,
        "description": subject.description,
    }


def professor_to_dict(professor: Professor) -> dict:
    """Convierte un profesor de la base de datos en un diccionario."""
    return {
        "id": professor.id,
        "name": professor.name,
        "subject_id": professor.subject_id,
        "public_profile_url": professor.public_profile_url,
        "notes": professor.notes,
    }


@mcp.tool()
def health_check() -> str:
    """Comprueba que el servidor UniCore está funcionando."""
    return "UniCore MCP funcionando correctamente"


# ------------------------------------------------------------------
# ASIGNATURAS
# ------------------------------------------------------------------


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
            select(Subject).where(
                func.lower(Subject.name) == clean_name.lower()
            )
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
                    "error": "El nombre no puede estar vacío",
                }

            duplicate = session.scalar(
                select(Subject).where(
                    func.lower(Subject.name) == clean_name.lower(),
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


# ------------------------------------------------------------------
# PROFESORES
# ------------------------------------------------------------------


@mcp.tool()
def create_professor(
    name: str,
    subject_id: int,
    public_profile_url: str | None = None,
    notes: str | None = None,
) -> dict:
    """Crea un profesor y lo vincula con una asignatura."""

    clean_name = name.strip()

    if not clean_name:
        return {
            "ok": False,
            "error": "El nombre del profesor no puede estar vacío",
        }

    with SessionLocal() as session:
        subject = session.get(Subject, subject_id)

        if subject is None:
            return {
                "ok": False,
                "error": "La asignatura indicada no existe",
            }

        existing_professor = session.scalar(
            select(Professor).where(
                func.lower(Professor.name) == clean_name.lower(),
                Professor.subject_id == subject_id,
            )
        )

        if existing_professor:
            return {
                "ok": False,
                "error": "Este profesor ya está vinculado a la asignatura",
                "professor_id": existing_professor.id,
            }

        professor = Professor(
            name=clean_name,
            subject_id=subject_id,
            public_profile_url=public_profile_url,
            notes=notes,
        )

        session.add(professor)
        session.commit()
        session.refresh(professor)

        return {
            "ok": True,
            "professor": professor_to_dict(professor),
            "subject": subject_to_dict(subject),
        }


@mcp.tool()
def list_professors(subject_id: int | None = None) -> list[dict]:
    """Lista profesores, opcionalmente filtrados por asignatura."""

    with SessionLocal() as session:
        query = select(Professor).order_by(Professor.name)

        if subject_id is not None:
            query = query.where(Professor.subject_id == subject_id)

        professors = session.scalars(query).all()

        return [professor_to_dict(professor) for professor in professors]


@mcp.tool()
def get_professor(professor_id: int) -> dict:
    """Devuelve un profesor concreto y su asignatura."""

    with SessionLocal() as session:
        professor = session.get(Professor, professor_id)

        if professor is None:
            return {
                "ok": False,
                "error": "Profesor no encontrado",
            }

        subject = session.get(Subject, professor.subject_id)

        return {
            "ok": True,
            "professor": professor_to_dict(professor),
            "subject": subject_to_dict(subject),
        }


@mcp.tool()
def delete_professor(professor_id: int) -> dict:
    """Elimina un profesor por su ID."""

    with SessionLocal() as session:
        professor = session.get(Professor, professor_id)

        if professor is None:
            return {
                "ok": False,
                "error": "Profesor no encontrado",
            }

        professor_data = professor_to_dict(professor)

        session.delete(professor)
        session.commit()

        return {
            "ok": True,
            "message": "Profesor eliminado correctamente",
            "professor": professor_data,
        }