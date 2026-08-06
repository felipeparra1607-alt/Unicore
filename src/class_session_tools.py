import re
from datetime import date, datetime

from sqlalchemy import or_, select

from src.database.connection import SessionLocal
from src.database.models import (
    ClassSession,
    Document,
    Professor,
    Subject,
)


SESSION_TEXT_FIELDS = (
    "title",
    "session_type",
    "location",
    "topics",
    "notes",
    "transcript",
    "summary",
    "doubts",
    "tasks",
)


def clean_optional_text(
    value: str | None,
) -> str | None:
    """Limpia un texto opcional."""

    if value is None:
        return None

    cleaned = value.strip()

    return cleaned or None


def parse_optional_date(
    value: str | None,
) -> date | None:
    """Convierte YYYY-MM-DD a fecha."""

    if value is None or not value.strip():
        return None

    return date.fromisoformat(
        value.strip()
    )


def validate_optional_time(
    value: str | None,
) -> str | None:
    """Valida horarios en formato HH:MM."""

    cleaned = clean_optional_text(value)

    if cleaned is None:
        return None

    if not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d",
        cleaned,
    ):
        raise ValueError(
            "El horario debe usar formato HH:MM"
        )

    return cleaned


def class_session_to_dict(
    class_session: ClassSession,
    subject: Subject | None = None,
    professor: Professor | None = None,
    document: Document | None = None,
    include_long_text: bool = True,
) -> dict:
    """Convierte una sesión en un diccionario MCP."""

    result = {
        "id": class_session.id,
        "title": class_session.title,
        "class_date": (
            class_session.class_date.isoformat()
            if class_session.class_date
            else None
        ),
        "start_time": class_session.start_time,
        "end_time": class_session.end_time,
        "session_type": class_session.session_type,
        "location": class_session.location,
        "attended": class_session.attended,
        "subject_id": class_session.subject_id,
        "subject_name": (
            subject.name
            if subject is not None
            else None
        ),
        "professor_id": class_session.professor_id,
        "professor_name": (
            professor.name
            if professor is not None
            else None
        ),
        "source_document_id": (
            class_session.source_document_id
        ),
        "source_document_title": (
            document.title
            if document is not None
            else None
        ),
        "topics": class_session.topics,
        "created_at": (
            class_session.created_at.isoformat()
            if class_session.created_at
            else None
        ),
        "updated_at": (
            class_session.updated_at.isoformat()
            if class_session.updated_at
            else None
        ),
    }

    if include_long_text:
        result.update({
            "notes": class_session.notes,
            "transcript": class_session.transcript,
            "summary": class_session.summary,
            "doubts": class_session.doubts,
            "tasks": class_session.tasks,
        })

    return result


def load_related_entities(
    session,
    class_session: ClassSession,
) -> tuple[
    Subject | None,
    Professor | None,
    Document | None,
]:
    """Carga las entidades relacionadas."""

    subject = session.get(
        Subject,
        class_session.subject_id,
    )

    professor = (
        session.get(
            Professor,
            class_session.professor_id,
        )
        if class_session.professor_id
        else None
    )

    document = (
        session.get(
            Document,
            class_session.source_document_id,
        )
        if class_session.source_document_id
        else None
    )

    return subject, professor, document


def validate_relations(
    session,
    subject_id: int,
    professor_id: int | None,
    source_document_id: int | None,
) -> tuple[
    Subject,
    Professor | None,
    Document | None,
]:
    """Valida asignatura, profesor y documento."""

    subject = session.get(
        Subject,
        subject_id,
    )

    if subject is None:
        raise ValueError(
            "La asignatura no existe"
        )

    professor = None

    if professor_id is not None:
        professor = session.get(
            Professor,
            professor_id,
        )

        if professor is None:
            raise ValueError(
                "El profesor no existe"
            )

        if professor.subject_id != subject_id:
            raise ValueError(
                "El profesor no pertenece "
                "a esta asignatura"
            )

    document = None

    if source_document_id is not None:
        document = session.get(
            Document,
            source_document_id,
        )

        if document is None:
            raise ValueError(
                "El documento no existe"
            )

        if (
            document.subject_id is not None
            and document.subject_id != subject_id
        ):
            raise ValueError(
                "El documento pertenece "
                "a otra asignatura"
            )

    return subject, professor, document


def register_class_session_tools(mcp) -> None:
    """Registra las tools de memoria de clases."""

    @mcp.tool()
    def create_class_session(
        title: str,
        subject_id: int,
        class_date: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        session_type: str | None = None,
        location: str | None = None,
        attended: bool = True,
        professor_id: int | None = None,
        source_document_id: int | None = None,
        topics: str | None = None,
        notes: str | None = None,
        transcript: str | None = None,
        summary: str | None = None,
        doubts: str | None = None,
        tasks: str | None = None,
    ) -> dict:
        """Crea una nueva sesión académica."""

        clean_title = title.strip()

        if not clean_title:
            return {
                "ok": False,
                "error": (
                    "El título no puede estar vacío"
                ),
            }

        try:
            parsed_date = parse_optional_date(
                class_date
            )

            parsed_start_time = validate_optional_time(
                start_time
            )

            parsed_end_time = validate_optional_time(
                end_time
            )

            if (
                parsed_start_time
                and parsed_end_time
                and parsed_end_time
                <= parsed_start_time
            ):
                return {
                    "ok": False,
                    "error": (
                        "La hora final debe ser posterior "
                        "a la hora inicial"
                    ),
                }

        except ValueError as error:
            return {
                "ok": False,
                "error": str(error),
            }

        with SessionLocal() as session:
            try:
                subject, professor, document = (
                    validate_relations(
                        session=session,
                        subject_id=subject_id,
                        professor_id=professor_id,
                        source_document_id=(
                            source_document_id
                        ),
                    )
                )

                duplicate_statement = select(
                    ClassSession
                ).where(
                    ClassSession.subject_id
                    == subject_id,
                    ClassSession.title
                    .ilike(clean_title),
                )

                if parsed_date is not None:
                    duplicate_statement = (
                        duplicate_statement.where(
                            ClassSession.class_date
                            == parsed_date
                        )
                    )

                duplicate = session.scalar(
                    duplicate_statement
                )

                if duplicate is not None:
                    return {
                        "ok": False,
                        "error": (
                            "Ya existe una sesión con "
                            "ese título y fecha"
                        ),
                        "existing_session_id": (
                            duplicate.id
                        ),
                    }

                class_session = ClassSession(
                    title=clean_title,
                    class_date=parsed_date,
                    start_time=parsed_start_time,
                    end_time=parsed_end_time,
                    session_type=clean_optional_text(
                        session_type
                    ),
                    location=clean_optional_text(
                        location
                    ),
                    attended=attended,
                    subject_id=subject_id,
                    professor_id=professor_id,
                    source_document_id=(
                        source_document_id
                    ),
                    topics=clean_optional_text(topics),
                    notes=clean_optional_text(notes),
                    transcript=clean_optional_text(
                        transcript
                    ),
                    summary=clean_optional_text(summary),
                    doubts=clean_optional_text(doubts),
                    tasks=clean_optional_text(tasks),
                    updated_at=datetime.utcnow(),
                )

                session.add(class_session)
                session.commit()
                session.refresh(class_session)

                return {
                    "ok": True,
                    "class_session": (
                        class_session_to_dict(
                            class_session,
                            subject=subject,
                            professor=professor,
                            document=document,
                        )
                    ),
                }

            except ValueError as error:
                return {
                    "ok": False,
                    "error": str(error),
                }

            except Exception as error:
                session.rollback()

                return {
                    "ok": False,
                    "error": (
                        "No se pudo crear la sesión"
                    ),
                    "technical_detail": str(error),
                }

    @mcp.tool()
    def list_class_sessions(
        subject_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        attended: bool | None = None,
        maximum_results: int = 100,
    ) -> dict:
        """Lista sesiones con filtros opcionales."""

        if maximum_results < 1 or maximum_results > 500:
            return {
                "ok": False,
                "error": (
                    "maximum_results debe estar "
                    "entre 1 y 500"
                ),
            }

        try:
            parsed_date_from = parse_optional_date(
                date_from
            )
            parsed_date_to = parse_optional_date(
                date_to
            )
        except ValueError:
            return {
                "ok": False,
                "error": (
                    "Las fechas deben usar YYYY-MM-DD"
                ),
            }

        with SessionLocal() as session:
            statement = select(
                ClassSession
            )

            if subject_id is not None:
                statement = statement.where(
                    ClassSession.subject_id
                    == subject_id
                )

            if parsed_date_from is not None:
                statement = statement.where(
                    ClassSession.class_date
                    >= parsed_date_from
                )

            if parsed_date_to is not None:
                statement = statement.where(
                    ClassSession.class_date
                    <= parsed_date_to
                )

            if attended is not None:
                statement = statement.where(
                    ClassSession.attended
                    == attended
                )

            statement = statement.order_by(
                ClassSession.class_date.desc(),
                ClassSession.start_time.desc(),
                ClassSession.id.desc(),
            ).limit(maximum_results)

            class_sessions = session.scalars(
                statement
            ).all()

            results = []

            for class_session in class_sessions:
                subject, professor, document = (
                    load_related_entities(
                        session,
                        class_session,
                    )
                )

                results.append(
                    class_session_to_dict(
                        class_session,
                        subject=subject,
                        professor=professor,
                        document=document,
                        include_long_text=False,
                    )
                )

            return {
                "ok": True,
                "result_count": len(results),
                "class_sessions": results,
            }

    @mcp.tool()
    def get_class_session(
        class_session_id: int,
    ) -> dict:
        """Obtiene todos los datos de una sesión."""

        with SessionLocal() as session:
            class_session = session.get(
                ClassSession,
                class_session_id,
            )

            if class_session is None:
                return {
                    "ok": False,
                    "error": (
                        "La sesión no existe"
                    ),
                }

            subject, professor, document = (
                load_related_entities(
                    session,
                    class_session,
                )
            )

            return {
                "ok": True,
                "class_session": class_session_to_dict(
                    class_session,
                    subject=subject,
                    professor=professor,
                    document=document,
                ),
            }

    @mcp.tool()
    def update_class_session(
        class_session_id: int,
        title: str | None = None,
        class_date: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        session_type: str | None = None,
        location: str | None = None,
        attended: bool | None = None,
        professor_id: int | None = None,
        source_document_id: int | None = None,
        topics: str | None = None,
        notes: str | None = None,
        transcript: str | None = None,
        summary: str | None = None,
        doubts: str | None = None,
        tasks: str | None = None,
    ) -> dict:
        """
        Actualiza una sesión.

        Los textos vacíos eliminan el contenido del campo.
        """

        with SessionLocal() as session:
            class_session = session.get(
                ClassSession,
                class_session_id,
            )

            if class_session is None:
                return {
                    "ok": False,
                    "error": (
                        "La sesión no existe"
                    ),
                }

            try:
                if title is not None:
                    clean_title = title.strip()

                    if not clean_title:
                        return {
                            "ok": False,
                            "error": (
                                "El título no puede "
                                "estar vacío"
                            ),
                        }

                    class_session.title = clean_title

                if class_date is not None:
                    class_session.class_date = (
                        parse_optional_date(
                            class_date
                        )
                    )

                if start_time is not None:
                    class_session.start_time = (
                        validate_optional_time(
                            start_time
                        )
                    )

                if end_time is not None:
                    class_session.end_time = (
                        validate_optional_time(
                            end_time
                        )
                    )

                if (
                    class_session.start_time
                    and class_session.end_time
                    and class_session.end_time
                    <= class_session.start_time
                ):
                    return {
                        "ok": False,
                        "error": (
                            "La hora final debe ser "
                            "posterior a la inicial"
                        ),
                    }

                if professor_id is not None:
                    professor = session.get(
                        Professor,
                        professor_id,
                    )

                    if professor is None:
                        return {
                            "ok": False,
                            "error": (
                                "El profesor no existe"
                            ),
                        }

                    if (
                        professor.subject_id
                        != class_session.subject_id
                    ):
                        return {
                            "ok": False,
                            "error": (
                                "El profesor pertenece "
                                "a otra asignatura"
                            ),
                        }

                    class_session.professor_id = (
                        professor_id
                    )

                if source_document_id is not None:
                    document = session.get(
                        Document,
                        source_document_id,
                    )

                    if document is None:
                        return {
                            "ok": False,
                            "error": (
                                "El documento no existe"
                            ),
                        }

                    if (
                        document.subject_id is not None
                        and document.subject_id
                        != class_session.subject_id
                    ):
                        return {
                            "ok": False,
                            "error": (
                                "El documento pertenece "
                                "a otra asignatura"
                            ),
                        }

                    class_session.source_document_id = (
                        source_document_id
                    )

                optional_text_updates = {
                    "session_type": session_type,
                    "location": location,
                    "topics": topics,
                    "notes": notes,
                    "transcript": transcript,
                    "summary": summary,
                    "doubts": doubts,
                    "tasks": tasks,
                }

                for field_name, value in (
                    optional_text_updates.items()
                ):
                    if value is not None:
                        setattr(
                            class_session,
                            field_name,
                            clean_optional_text(value),
                        )

                if attended is not None:
                    class_session.attended = attended

                class_session.updated_at = (
                    datetime.utcnow()
                )

                session.commit()
                session.refresh(class_session)

                subject, professor, document = (
                    load_related_entities(
                        session,
                        class_session,
                    )
                )

                return {
                    "ok": True,
                    "class_session": (
                        class_session_to_dict(
                            class_session,
                            subject=subject,
                            professor=professor,
                            document=document,
                        )
                    ),
                }

            except ValueError as error:
                session.rollback()

                return {
                    "ok": False,
                    "error": str(error),
                }

            except Exception as error:
                session.rollback()

                return {
                    "ok": False,
                    "error": (
                        "No se pudo actualizar "
                        "la sesión"
                    ),
                    "technical_detail": str(error),
                }

    @mcp.tool()
    def delete_class_session(
        class_session_id: int,
    ) -> dict:
        """Elimina una sesión de la memoria."""

        with SessionLocal() as session:
            class_session = session.get(
                ClassSession,
                class_session_id,
            )

            if class_session is None:
                return {
                    "ok": False,
                    "error": (
                        "La sesión no existe"
                    ),
                }

            deleted_title = class_session.title

            session.delete(class_session)
            session.commit()

            return {
                "ok": True,
                "deleted_class_session_id": (
                    class_session_id
                ),
                "deleted_title": deleted_title,
            }

    @mcp.tool()
    def search_class_sessions(
        query: str,
        subject_id: int | None = None,
        maximum_results: int = 20,
    ) -> dict:
        """Busca palabras dentro de la memoria de clases."""

        clean_query = query.strip()

        if not clean_query:
            return {
                "ok": False,
                "error": (
                    "La búsqueda no puede estar vacía"
                ),
            }

        if maximum_results < 1 or maximum_results > 100:
            return {
                "ok": False,
                "error": (
                    "maximum_results debe estar "
                    "entre 1 y 100"
                ),
            }

        search_pattern = f"%{clean_query}%"

        with SessionLocal() as session:
            text_conditions = [
                getattr(
                    ClassSession,
                    field_name,
                ).ilike(search_pattern)
                for field_name in SESSION_TEXT_FIELDS
            ]

            statement = select(
                ClassSession
            ).where(
                or_(*text_conditions)
            )

            if subject_id is not None:
                statement = statement.where(
                    ClassSession.subject_id
                    == subject_id
                )

            statement = statement.order_by(
                ClassSession.class_date.desc(),
                ClassSession.id.desc(),
            ).limit(maximum_results)

            class_sessions = session.scalars(
                statement
            ).all()

            results = []

            for class_session in class_sessions:
                subject, professor, document = (
                    load_related_entities(
                        session,
                        class_session,
                    )
                )

                results.append(
                    class_session_to_dict(
                        class_session,
                        subject=subject,
                        professor=professor,
                        document=document,
                    )
                )

            return {
                "ok": True,
                "query": clean_query,
                "result_count": len(results),
                "class_sessions": results,
            }

    @mcp.tool()
    def build_subject_class_timeline(
        subject_id: int,
        maximum_sessions: int = 50,
        include_transcripts: bool = False,
    ) -> dict:
        """
        Construye una memoria cronológica de una asignatura.
        """

        if maximum_sessions < 1 or maximum_sessions > 200:
            return {
                "ok": False,
                "error": (
                    "maximum_sessions debe estar "
                    "entre 1 y 200"
                ),
            }

        with SessionLocal() as session:
            subject = session.get(
                Subject,
                subject_id,
            )

            if subject is None:
                return {
                    "ok": False,
                    "error": (
                        "La asignatura no existe"
                    ),
                }

            class_sessions = session.scalars(
                select(ClassSession)
                .where(
                    ClassSession.subject_id
                    == subject_id
                )
                .order_by(
                    ClassSession.class_date.asc(),
                    ClassSession.start_time.asc(),
                    ClassSession.id.asc(),
                )
                .limit(maximum_sessions)
            ).all()

            timeline_blocks = []

            for class_session in class_sessions:
                date_label = (
                    class_session.class_date.isoformat()
                    if class_session.class_date
                    else "Fecha no registrada"
                )

                heading = (
                    f"[SESIÓN {class_session.id}] "
                    f"{date_label} — "
                    f"{class_session.title}"
                )

                details = [
                    heading,
                    (
                        "Asistencia: "
                        + (
                            "sí"
                            if class_session.attended
                            else "no"
                        )
                    ),
                ]

                if class_session.topics:
                    details.append(
                        f"Temas: {class_session.topics}"
                    )

                if class_session.summary:
                    details.append(
                        f"Resumen: {class_session.summary}"
                    )

                if class_session.notes:
                    details.append(
                        f"Apuntes: {class_session.notes}"
                    )

                if class_session.doubts:
                    details.append(
                        f"Dudas: {class_session.doubts}"
                    )

                if class_session.tasks:
                    details.append(
                        f"Tareas: {class_session.tasks}"
                    )

                if (
                    include_transcripts
                    and class_session.transcript
                ):
                    details.append(
                        "Transcripción: "
                        f"{class_session.transcript}"
                    )

                timeline_blocks.append(
                    "\n".join(details)
                )

            timeline = "\n\n---\n\n".join(
                timeline_blocks
            )

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "session_count": len(
                    class_sessions
                ),
                "timeline_characters": len(
                    timeline
                ),
                "timeline": timeline,
            }