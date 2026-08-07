import hashlib
from pathlib import Path

from mcp.server import MCPServer
from sqlalchemy import func, select

from src.chunk_tools import register_chunk_tools
from src.model_answer_tools import register_model_answer_tools
from src.database.connection import SessionLocal
from src.database.models import Document, Professor, Subject
from src.rag_answer_tools import register_rag_answer_tools
from src.rag_tools import register_rag_tools
from src.review_tools import register_review_tools
from src.study_tools import register_study_tools
from src.assessment_tools import (
    register_assessment_tools,
)
from src.grade_planner_tools import (
    register_grade_planner_tools,
)
from src.academic_task_tools import (
    register_academic_task_tools,
)
from src.task_planner_tools import (
    register_task_planner_tools,
)
from src.dashboard_tools import (
    register_dashboard_tools,
)
from src.study_progress_tools import (
    register_study_progress_tools,
)
from src.class_session_tools import (
    register_class_session_tools,
)
from src.document_extractors import (
    SUPPORTED_EXTENSIONS,
    extract_document_text as extract_text_from_file,
)
from src.study_session_tools import (
    register_study_session_tools,
)
from src.professor_rubric_tools import (
    register_professor_rubric_tools,
)
from src.assignment_preparation_tools import (
    register_assignment_preparation_tools,
)

mcp = MCPServer("UniCore")
register_chunk_tools(mcp)
register_rag_tools(mcp)
register_rag_answer_tools(mcp)
register_model_answer_tools(mcp)
register_class_session_tools(mcp)
register_study_tools(mcp)
register_study_progress_tools(mcp)
register_review_tools(mcp)
register_dashboard_tools(mcp)
register_study_session_tools(mcp)
register_academic_task_tools(mcp)
register_task_planner_tools(mcp)
register_assessment_tools(mcp)
register_grade_planner_tools(mcp)
register_professor_rubric_tools(mcp)
register_assignment_preparation_tools(mcp)


def subject_to_dict(subject: Subject) -> dict:
    return {
        "id": subject.id,
        "name": subject.name,
        "academic_year": subject.academic_year,
        "description": subject.description,
    }


def professor_to_dict(professor: Professor) -> dict:
    return {
        "id": professor.id,
        "name": professor.name,
        "subject_id": professor.subject_id,
        "public_profile_url": professor.public_profile_url,
        "notes": professor.notes,
    }


def document_to_dict(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "file_path": document.file_path,
        "file_type": document.file_type,
        "document_type": document.document_type,
        "subject_id": document.subject_id,
        "content_hash": document.content_hash,
        "has_extracted_text": bool(document.extracted_text),
        "extracted_text_length": len(document.extracted_text or ""),
    }


def calculate_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            sha256.update(chunk)

    return sha256.hexdigest()


def register_document_record(
    file_path: str,
    subject_id: int | None = None,
    title: str | None = None,
    document_type: str | None = None,
) -> dict:
    """Lógica interna reutilizable para registrar documentos."""

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
            select(Document).where(
                Document.content_hash == content_hash
            )
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
def health_check() -> str:
    """Comprueba que el servidor UniCore está funcionando."""
    return "UniCore MCP funcionando correctamente"


# ================================================================
# ASIGNATURAS
# ================================================================


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

        return [
            subject_to_dict(subject)
            for subject in subjects
        ]


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
    """Elimina una asignatura."""

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


# ================================================================
# PROFESORES
# ================================================================


@mcp.tool()
def create_professor(
    name: str,
    subject_id: int,
    public_profile_url: str | None = None,
    notes: str | None = None,
) -> dict:
    """Crea un profesor y lo vincula a una asignatura."""

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
def list_professors(
    subject_id: int | None = None,
) -> list[dict]:
    """Lista profesores, opcionalmente por asignatura."""

    with SessionLocal() as session:
        query = select(Professor).order_by(Professor.name)

        if subject_id is not None:
            query = query.where(
                Professor.subject_id == subject_id
            )

        professors = session.scalars(query).all()

        return [
            professor_to_dict(professor)
            for professor in professors
        ]


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

        subject = session.get(
            Subject,
            professor.subject_id,
        )

        return {
            "ok": True,
            "professor": professor_to_dict(professor),
            "subject": subject_to_dict(subject),
        }


@mcp.tool()
def delete_professor(professor_id: int) -> dict:
    """Elimina un profesor."""

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


# ================================================================
# DOCUMENTOS
# ================================================================


@mcp.tool()
def register_document(
    file_path: str,
    subject_id: int | None = None,
    title: str | None = None,
    document_type: str | None = None,
) -> dict:
    """Registra un archivo sin modificar el original."""

    return register_document_record(
        file_path=file_path,
        subject_id=subject_id,
        title=title,
        document_type=document_type,
    )


@mcp.tool()
def import_folder(
    folder_path: str,
    subject_id: int | None = None,
    document_type: str | None = None,
    recursive: bool = True,
) -> dict:
    """Registra todos los documentos compatibles de una carpeta."""

    folder = Path(folder_path).expanduser().resolve()

    if not folder.exists():
        return {
            "ok": False,
            "error": "La carpeta indicada no existe",
            "folder_path": str(folder),
        }

    if not folder.is_dir():
        return {
            "ok": False,
            "error": "La ruta indicada no es una carpeta",
            "folder_path": str(folder),
        }

    if subject_id is not None:
        with SessionLocal() as session:
            if session.get(Subject, subject_id) is None:
                return {
                    "ok": False,
                    "error": "La asignatura indicada no existe",
                }

    iterator = folder.rglob("*") if recursive else folder.glob("*")

    compatible_files = sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    imported: list[dict] = []
    duplicates: list[dict] = []
    errors: list[dict] = []

    for file_path in compatible_files:
        result = register_document_record(
            file_path=str(file_path),
            subject_id=subject_id,
            document_type=document_type,
        )

        if result.get("ok"):
            imported.append(result["document"])
        elif result.get("error") == "Este archivo ya está registrado":
            duplicates.append(result["document"])
        else:
            errors.append({
                "file_path": str(file_path),
                "error": result.get("error"),
            })

    return {
        "ok": True,
        "folder_path": str(folder),
        "compatible_files_found": len(compatible_files),
        "imported_count": len(imported),
        "duplicate_count": len(duplicates),
        "error_count": len(errors),
        "imported": imported,
        "duplicates": duplicates,
        "errors": errors,
    }


@mcp.tool()
def list_documents(
    subject_id: int | None = None,
) -> list[dict]:
    """Lista documentos, opcionalmente por asignatura."""

    with SessionLocal() as session:
        query = select(Document).order_by(Document.title)

        if subject_id is not None:
            query = query.where(
                Document.subject_id == subject_id
            )

        documents = session.scalars(query).all()

        return [
            document_to_dict(document)
            for document in documents
        ]


@mcp.tool()
def get_document(document_id: int) -> dict:
    """Devuelve los metadatos de un documento."""

    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "ok": False,
                "error": "Documento no encontrado",
            }

        subject = None

        if document.subject_id is not None:
            subject_record = session.get(
                Subject,
                document.subject_id,
            )

            if subject_record is not None:
                subject = subject_to_dict(subject_record)

        return {
            "ok": True,
            "document": document_to_dict(document),
            "subject": subject,
        }


@mcp.tool()
def update_document(
    document_id: int,
    title: str | None = None,
    document_type: str | None = None,
    subject_id: int | None = None,
) -> dict:
    """Actualiza los metadatos de un documento."""

    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "ok": False,
                "error": "Documento no encontrado",
            }

        if title is not None:
            clean_title = title.strip()

            if not clean_title:
                return {
                    "ok": False,
                    "error": "El título no puede estar vacío",
                }

            document.title = clean_title

        if document_type is not None:
            document.document_type = (
                document_type.strip() or None
            )

        if subject_id is not None:
            subject = session.get(Subject, subject_id)

            if subject is None:
                return {
                    "ok": False,
                    "error": "La asignatura indicada no existe",
                }

            document.subject_id = subject_id

        session.commit()
        session.refresh(document)

        return {
            "ok": True,
            "document": document_to_dict(document),
        }


@mcp.tool()
def extract_document_text(document_id: int) -> dict:
    """Extrae y guarda el texto de un documento registrado."""

    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "ok": False,
                "error": "Documento no encontrado",
            }

        path = Path(document.file_path)

        if not path.exists():
            return {
                "ok": False,
                "error": "El archivo original ya no existe",
                "file_path": document.file_path,
            }

        try:
            extracted_text = extract_text_from_file(path)
        except ValueError as error:
            return {
                "ok": False,
                "error": str(error),
            }
        except Exception as error:
            return {
                "ok": False,
                "error": "No se pudo extraer el texto",
                "technical_detail": str(error),
            }

        cleaned_text = extracted_text.strip()

        if not cleaned_text:
            return {
                "ok": False,
                "error": (
                    "No se encontró texto extraíble. "
                    "El archivo podría estar vacío o necesitar OCR."
                ),
            }

        document.extracted_text = cleaned_text

        session.commit()
        session.refresh(document)

        return {
            "ok": True,
            "document": document_to_dict(document),
            "characters_extracted": len(cleaned_text),
            "preview": cleaned_text[:500],
        }


@mcp.tool()
def extract_pending_documents(
    subject_id: int | None = None,
    limit: int = 50,
) -> dict:
    """Extrae en lote documentos que todavía no tienen texto."""

    if limit < 1 or limit > 500:
        return {
            "ok": False,
            "error": "El límite debe estar entre 1 y 500",
        }

    with SessionLocal() as session:
        query = select(Document).where(
            Document.extracted_text.is_(None)
        )

        if subject_id is not None:
            query = query.where(
                Document.subject_id == subject_id
            )

        documents = session.scalars(
            query.order_by(Document.id).limit(limit)
        ).all()

        document_ids = [
            document.id
            for document in documents
        ]

    successful: list[dict] = []
    failed: list[dict] = []

    for document_id in document_ids:
        result = extract_document_text(document_id)

        if result.get("ok"):
            successful.append({
                "document_id": document_id,
                "characters_extracted": result[
                    "characters_extracted"
                ],
            })
        else:
            failed.append({
                "document_id": document_id,
                "error": result.get("error"),
            })

    return {
        "ok": True,
        "processed_count": len(document_ids),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "successful": successful,
        "failed": failed,
    }


@mcp.tool()
def get_document_text(
    document_id: int,
    max_characters: int = 12000,
) -> dict:
    """Devuelve el texto extraído de un documento."""

    if max_characters < 100 or max_characters > 100000:
        return {
            "ok": False,
            "error": (
                "max_characters debe estar entre 100 y 100000"
            ),
        }

    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "ok": False,
                "error": "Documento no encontrado",
            }

        if not document.extracted_text:
            return {
                "ok": False,
                "error": "El documento todavía no tiene texto extraído",
            }

        full_text = document.extracted_text
        returned_text = full_text[:max_characters]

        return {
            "ok": True,
            "document": document_to_dict(document),
            "text": returned_text,
            "returned_characters": len(returned_text),
            "total_characters": len(full_text),
            "truncated": len(returned_text) < len(full_text),
        }


@mcp.tool()
def search_document_text(
    query: str,
    subject_id: int | None = None,
    max_results: int = 10,
) -> dict:
    """Busca texto literal dentro de los documentos extraídos."""

    clean_query = query.strip()

    if not clean_query:
        return {
            "ok": False,
            "error": "La búsqueda no puede estar vacía",
        }

    if max_results < 1 or max_results > 50:
        return {
            "ok": False,
            "error": "max_results debe estar entre 1 y 50",
        }

    with SessionLocal() as session:
        statement = select(Document).where(
            Document.extracted_text.is_not(None)
        )

        if subject_id is not None:
            statement = statement.where(
                Document.subject_id == subject_id
            )

        documents = session.scalars(statement).all()

        results: list[dict] = []
        normalized_query = clean_query.casefold()

        for document in documents:
            text = document.extracted_text or ""
            normalized_text = text.casefold()
            position = normalized_text.find(normalized_query)

            if position == -1:
                continue

            start = max(0, position - 180)
            end = min(
                len(text),
                position + len(clean_query) + 320,
            )

            results.append({
                "document": document_to_dict(document),
                "match_position": position,
                "snippet": text[start:end].strip(),
            })

            if len(results) >= max_results:
                break

        return {
            "ok": True,
            "query": clean_query,
            "result_count": len(results),
            "results": results,
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
            "message": "Registro eliminado correctamente",
            "original_file_deleted": False,
            "document": document_data,
        }