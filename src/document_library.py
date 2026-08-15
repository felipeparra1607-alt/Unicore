from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from sqlalchemy import func, select

from src.chunk_tools import generate_chunks_for_document
from src.curriculum_engine import build_curriculum_for_document
from src.database.connection import DATA_DIR, SessionLocal
from src.database.models import Document, DocumentChunk, Subject
from src.document_extractors import SUPPORTED_EXTENSIONS, extract_document_text
from src.server import register_document_record


MAXIMUM_DOCUMENT_BYTES = 8 * 1024 * 1024
MANAGED_DOCUMENTS_DIR = DATA_DIR / "materials"


def _serialize_document(document: Document, chunk_count: int | None = None) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "file_type": document.file_type,
        "document_type": document.document_type,
        "academic_year": document.academic_year,
        "semester": document.semester,
        "professor_id": document.professor_id,
        "subject_id": document.subject_id,
        "has_extracted_text": bool(document.extracted_text),
        "character_count": len(document.extracted_text or ""),
        "chunk_count": chunk_count if chunk_count is not None else len(document.chunks),
        "created_at": document.created_at.isoformat() if document.created_at else None,
    }


def _validate_upload(file_name: str, content: bytes) -> tuple[str, str]:
    clean_name = str(file_name or "").strip()
    if not clean_name or Path(clean_name).name != clean_name:
        raise ValueError("El nombre del archivo no es válido")
    extension = Path(clean_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        formats = ", ".join(item.removeprefix(".").upper() for item in sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Formato no compatible. Usa: {formats}")
    if not content:
        raise ValueError("El archivo está vacío")
    if len(content) > MAXIMUM_DOCUMENT_BYTES:
        raise ValueError("El archivo supera el límite de 8 MB")
    return clean_name, extension


def ingest_document_bytes(
    *,
    file_name: str,
    content: bytes,
    subject_id: int,
    title: str | None = None,
    document_type: str = "course_material",
    academic_year: str | None = None,
    semester: str | None = None,
    professor_id: int | None = None,
) -> dict:
    """Persiste y prepara un material reutilizando el pipeline documental."""

    clean_name, extension = _validate_upload(file_name, content)
    content_hash = hashlib.sha256(content).hexdigest()

    with SessionLocal() as session:
        if session.get(Subject, subject_id) is None:
            raise ValueError("La asignatura indicada no existe")
        duplicate = session.scalar(select(Document).where(Document.content_hash == content_hash))
        if duplicate is not None:
            if duplicate.subject_id != subject_id:
                raise ValueError(
                    "Este material ya está guardado en otra asignatura; no se duplicó."
                )
            return {
                "ok": True,
                "duplicate": True,
                "message": "Este material ya estaba guardado; no se volvió a procesar.",
                "document": _serialize_document(duplicate),
            }

    MANAGED_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    final_path = (MANAGED_DOCUMENTS_DIR / f"{content_hash}{extension}").resolve()
    if MANAGED_DOCUMENTS_DIR.resolve() not in final_path.parents:
        raise ValueError("No se pudo crear una ruta segura para el archivo")
    temporary_path = final_path.with_suffix(final_path.suffix + ".uploading")
    temporary_path.write_bytes(content)
    temporary_path.replace(final_path)

    registered_id: int | None = None
    try:
        registered = register_document_record(
            file_path=str(final_path),
            subject_id=subject_id,
            title=(str(title or "").strip() or Path(clean_name).stem),
            document_type=document_type,
        )
        if not registered.get("ok"):
            duplicate = registered.get("document")
            if duplicate:
                if duplicate.get("subject_id") != subject_id:
                    final_path.unlink(missing_ok=True)
                    raise ValueError(
                        "Este material ya está guardado en otra asignatura; no se duplicó."
                    )
                final_path.unlink(missing_ok=True)
                return {
                    "ok": True,
                    "duplicate": True,
                    "message": "Este material ya estaba guardado; no se volvió a procesar.",
                    "document": duplicate,
                }
            raise RuntimeError(registered.get("error") or "No se pudo registrar el material")
        registered_id = int(registered["document"]["id"])

        extracted = extract_document_text(final_path).strip()
        if not extracted:
            raise ValueError("No se encontró texto extraíble. El archivo puede necesitar OCR.")

        with SessionLocal() as session:
            document = session.get(Document, registered_id)
            if document is None:
                raise RuntimeError("El material dejó de estar disponible durante la preparación")
            document.extracted_text = extracted
            document.academic_year = academic_year
            document.semester = semester
            document.professor_id = professor_id
            session.commit()

        chunk_result = generate_chunks_for_document(registered_id)
        if not chunk_result.get("ok"):
            raise RuntimeError(chunk_result.get("error") or "No se pudo preparar la búsqueda")

        curriculum_result = build_curriculum_for_document(registered_id)
        if not curriculum_result.get("ok"):
            raise RuntimeError(curriculum_result.get("error") or "No se pudo construir el temario")

        with SessionLocal() as session:
            document = session.get(Document, registered_id)
            if document is None:
                raise RuntimeError("El material preparado no está disponible")
            return {
                "ok": True,
                "duplicate": False,
                "message": "Material listo para consultar con UniCore.",
                "document": _serialize_document(document, int(chunk_result["chunk_count"])),
                "curriculum": curriculum_result,
            }
    except Exception:
        if registered_id is not None:
            with SessionLocal() as session:
                document = session.get(Document, registered_id)
                if document is not None:
                    session.delete(document)
                    session.commit()
        final_path.unlink(missing_ok=True)
        temporary_path.unlink(missing_ok=True)
        raise


def get_document_content(document_id: int) -> dict | None:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None
        chunk_count = session.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
        ) or 0
        return {
            "ok": True,
            "document": _serialize_document(document, int(chunk_count)),
            "content": document.extracted_text or "",
        }


def get_document_file(document_id: int) -> tuple[Path, str, str] | None:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None
        path = Path(document.file_path).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return None
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path, media_type, document.title


def delete_managed_document(document_id: int) -> bool:
    """Elimina solo documentos cuyo archivo está dentro del almacén gestionado."""

    managed_root = MANAGED_DOCUMENTS_DIR.resolve()
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            return False
        path = Path(document.file_path).expanduser().resolve()
        if managed_root not in path.parents:
            raise ValueError("Solo pueden eliminarse materiales subidos desde UniCore")
        session.delete(document)
        session.commit()
    path.unlink(missing_ok=True)
    return True
