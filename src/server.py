import hashlib
from pathlib import Path

from mcp.server import MCPServer
from sqlalchemy import func, select

from src.database.connection import SessionLocal
from src.database.models import Document, Professor, Subject


mcp = MCPServer("UniCore")


def subject_to_dict(subject: Subject) -> dict:
    """Convierte una asignatura en un diccionario."""
    return {
        "id": subject.id,
        "name": subject.name,
        "academic_year": subject.academic_year,
        "description": subject.description,
    }


def professor_to_dict(professor: Professor) -> dict:
    """Convierte un profesor en un diccionario."""
    return {
        "id": professor.id,
        "name": professor.name,
        "subject_id": professor.subject_id,
        "public_profile_url": professor.public_profile_url,
        "notes": professor.notes,
    }


def document_to_dict(document: Document) -> dict:
    """Convierte un documento en un diccionario."""
    return {
        "id": document.id,
        "title": document.title,
        "file_path": document.file_path,
        "file_type": document.file_type,
        "document_type": document.document_type,
        "subject_id": document.subject_id,
        "content_hash": document.content_hash,
        "has_extracted_text": bool(document.extracted_text),
    }


def calculate_file_hash(file_path: Path) -> str:
    """Calcula una huella SHA-256 para detectar archivos duplicados."""
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            sha256.update(chunk)

    return sha256.hexdigest()


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
    """Crea una nueva asignatura."""

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
    """Devuelve todas las asignaturas."""

    with SessionLocal() as session:
        subjects = session.scalars(
            select(Subject).order_by(Subject.name)
        ).all()

        return [subject_to_dict(subject) for subject in subjects]


@mcp.tool()
def get_subject(subject_id: int) -> dict:
    """Devuelve una asignatura por su ID."""

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
    """Actualiza una asignatura."""

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
    """Lista profesores, opcionalmente por asignatura."""

    with SessionLocal() as session:
        query = select(Professor).order_by(Professor.name)

        if subject_id is not None:
            query = query.where(Professor.subject_id == subject_id)

        professors = session.scalars(query).all()

        return [professor_to_dict(professor) for professor in professors]


@mcp.tool()
def get_professor(professor_id: int) -> dict:
    """Devuelve un profesor y su asignatura."""

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


# ------------------------------------------------------------------
# DOCUMENTOS
# ------------------------------------------------------------------


@mcp.tool()
def register_document(
    file_path: str,
    subject_id: int | None = None,
    title: str | None = None,
    document_type: str | None = None,
) -> dict:
    """Registra un archivo universitario sin copiarlo ni borrarlo."""

    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        return {
            "ok": False,
            "error": "El archivo indicado no existe",
            "file_path": str(path),
        }

    if not path.is_file():
        return {
            "ok": False,
            "error": "La ruta indicada no corresponde a un archivo",
            "file_path": str(path),
        }

    content_hash = calculate_file_hash(path)

    with SessionLocal() as session:
        if subject_id is not None:
            subject = session.get(Subject, subject_id)

            if subject is None:
                return {
                    "ok": False,
                    "error": "La asignatura indicada no existe",
                }

        duplicate = session.scalar(
            select(Document).where(Document.content_hash == content_hash)
        )

        if duplicate:
            return {
                "ok": False,
                "error": "Este archivo ya está registrado",
                "document": document_to_dict(duplicate),
            }

        document = Document(
            title=title.strip() if title and title.strip() else path.stem,
            file_path=str(path),
            file_type=path.suffix.lower().lstrip(".") or None,
            document_type=document_type,
            subject_id=subject_id,
            content_hash=content_hash,
        )

        session.add(document)
        session.commit()
        session.refresh(document)

        return {
            "ok": True,
            "document": document_to_dict(document),
        }


@mcp.tool()
def list_documents(subject_id: int | None = None) -> list[dict]:
    """Lista documentos, opcionalmente filtrados por asignatura."""

    with SessionLocal() as session:
        query = select(Document).order_by(Document.title)

        if subject_id is not None:
            query = query.where(Document.subject_id == subject_id)

        documents = session.scalars(query).all()

        return [document_to_dict(document) for document in documents]


@mcp.tool()
def get_document(document_id: int) -> dict:
    """Devuelve un documento concreto."""

    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "ok": False,
                "error": "Documento no encontrado",
            }

        subject = None

        if document.subject_id is not None:
            subject_record = session.get(Subject, document.subject_id)

            if subject_record is not None:
                subject = subject_to_dict(subject_record)

        return {
            "ok": True,
            "document": document_to_dict(document),
            "subject": subject,
        }


@mcp.tool()
def delete_document(document_id: int) -> dict:
    """
    Elimina el registro de un documento.

    No elimina el archivo original del ordenador.
    """

    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "ok": False,
                "error": "Documento no encontrado",
            }

        document_data = document_to_dict(document)

        session.delete(document)
        session.commit()

        return {
            "ok": True,
            "message": "Registro del documento eliminado correctamente",
            "original_file_deleted": False,
            "document": document_data,
        }