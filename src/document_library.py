from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from sqlalchemy import func, select

from src.chunk_tools import generate_chunks_for_document
from src.curriculum_engine import build_curriculum_for_document
from src.database.connection import DATA_DIR, SessionLocal
from src.database.models import Document, DocumentChunk, Subject
from src.document_extractors import SUPPORTED_EXTENSIONS, extract_document_text
from src.server import register_document_record


MAXIMUM_DOCUMENT_BYTES = 50 * 1024 * 1024
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
        "processing_status": document.processing_status,
        "processing_stage": document.processing_stage,
        "processing_error": document.processing_error,
        "created_at": document.created_at.isoformat() if document.created_at else None,
    }


def _validate_upload(file_name: str, size_bytes: int) -> tuple[str, str]:
    clean_name = str(file_name or "").strip()
    if not clean_name or Path(clean_name).name != clean_name:
        raise ValueError("El nombre del archivo no es válido")
    extension = Path(clean_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        formats = ", ".join(item.removeprefix(".").upper() for item in sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Formato no compatible. Usa: {formats}")
    if size_bytes <= 0:
        raise ValueError("El archivo está vacío")
    if size_bytes > MAXIMUM_DOCUMENT_BYTES:
        raise ValueError("El archivo supera el límite de 50 MB")
    return clean_name, extension


def _hash_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _update_processing(document_id: int, status: str, stage: str | None, error: str | None = None) -> None:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        document.processing_status = status
        document.processing_stage = stage
        document.processing_error = error
        session.commit()


def prepare_document(document_id: int) -> dict:
    """Extrae, indexa y organiza un documento ya persistido.

    Se ejecuta fuera de la petición HTTP; un fallo conserva el archivo para que el
    usuario pueda ver qué ocurrió y reintentar sin volver a subirlo.
    """
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise ValueError("El material ya no está disponible")
        file_path = Path(document.file_path)

    try:
        _update_processing(document_id, "processing", "Extrayendo contenido…")
        extracted = extract_document_text(file_path).strip()
        if not extracted:
            raise ValueError("No se encontró texto extraíble. El archivo puede necesitar OCR.")
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is None:
                raise ValueError("El material ya no está disponible")
            document.extracted_text = extracted
            session.commit()

        _update_processing(document_id, "processing", "Preparando búsqueda…")
        chunk_result = generate_chunks_for_document(document_id)
        if not chunk_result.get("ok"):
            raise RuntimeError(chunk_result.get("error") or "No se pudo preparar la búsqueda")

        _update_processing(document_id, "processing", "Organizando temario…")
        curriculum_result = build_curriculum_for_document(document_id)
        if not curriculum_result.get("ok"):
            raise RuntimeError(curriculum_result.get("error") or "No se pudo organizar el temario")

        _update_processing(document_id, "ready", "Listo")
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            return {
                "ok": True,
                "document": _serialize_document(document, int(chunk_result["chunk_count"])),
                "curriculum": curriculum_result,
            }
    except Exception as error:
        _update_processing(document_id, "error", "No se pudo preparar", str(error))
        raise


def prepare_document_safely(document_id: int) -> None:
    """Ejecuta el pipeline en background sin propagar errores al servidor HTTP."""
    try:
        prepare_document(document_id)
    except Exception:
        return


def queue_document_processing(document_id: int) -> dict:
    """Marca un material persistido para reintento antes de lanzar el worker."""
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise ValueError("El material no existe")
        if not Path(document.file_path).is_file():
            raise ValueError("El archivo guardado ya no está disponible")
        if document.processing_status == "processing":
            raise RuntimeError("El material ya se está procesando")
        document.processing_status = "processing"
        document.processing_stage = "Extrayendo contenido…"
        document.processing_error = None
        session.commit()
        return _serialize_document(document)


def ingest_document_file(
    *,
    temporary_path: Path,
    file_name: str,
    subject_id: int,
    title: str | None = None,
    document_type: str = "course_material",
    academic_year: str | None = None,
    semester: str | None = None,
    professor_id: int | None = None,
) -> dict:
    """Registra un upload binario ya escrito en disco, sin cargarlo en memoria."""
    final_path: Path | None = None
    try:
        size_bytes = temporary_path.stat().st_size if temporary_path.is_file() else 0
        clean_name, extension = _validate_upload(file_name, size_bytes)
        content_hash = _hash_file(temporary_path)
        with SessionLocal() as session:
            if session.get(Subject, subject_id) is None:
                raise ValueError("La asignatura indicada no existe")
            duplicate = session.scalar(select(Document).where(Document.content_hash == content_hash))
            if duplicate is not None:
                if duplicate.subject_id != subject_id:
                    raise ValueError("Este material ya está guardado en otra asignatura; no se duplicó.")
                return {"ok": True, "duplicate": True, "message": "Este material ya estaba guardado; no se volvió a procesar.", "document": _serialize_document(duplicate)}

        MANAGED_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        final_path = (MANAGED_DOCUMENTS_DIR / f"{content_hash}{extension}").resolve()
        if MANAGED_DOCUMENTS_DIR.resolve() not in final_path.parents:
            raise ValueError("No se pudo crear una ruta segura para el archivo")
        shutil.move(str(temporary_path), str(final_path))
        registered = register_document_record(file_path=str(final_path), subject_id=subject_id, title=(str(title or "").strip() or Path(clean_name).stem), document_type=document_type)
        if not registered.get("ok"):
            final_path.unlink(missing_ok=True)
            raise RuntimeError(registered.get("error") or "No se pudo registrar el material")
        document_id = int(registered["document"]["id"])
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            document.academic_year = academic_year
            document.semester = semester
            document.professor_id = professor_id
            document.processing_status = "processing"
            document.processing_stage = "Extrayendo contenido…"
            document.processing_error = None
            session.commit()
            payload = _serialize_document(document, 0)
        return {"ok": True, "duplicate": False, "message": "Archivo guardado; UniCore lo está preparando.", "document": payload}
    finally:
        temporary_path.unlink(missing_ok=True)


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

    MANAGED_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = MANAGED_DOCUMENTS_DIR / f".legacy-{hashlib.sha256(content).hexdigest()}.uploading"
    temporary_path.write_bytes(content)
    stored = ingest_document_file(
        temporary_path=temporary_path,
        file_name=file_name,
        subject_id=subject_id,
        title=title,
        document_type=document_type,
        academic_year=academic_year,
        semester=semester,
        professor_id=professor_id,
    )
    if stored.get("duplicate"):
        return stored
    prepared = prepare_document(int(stored["document"]["id"]))
    return {
        **prepared,
        "duplicate": False,
        "message": "Material listo para consultar con UniCore.",
    }


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
