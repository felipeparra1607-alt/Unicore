from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import delete, select

from src.database.connection import SessionLocal
from src.database.models import (
    Conversation,
    ConversationMessage,
    Document,
    Subject,
)
from src.runtime_context import create_conversation_id


RECENT_MESSAGE_LIMIT = 8
RECENT_CHARACTER_LIMIT = 5000
SUMMARY_CHARACTER_LIMIT = 3600
SUMMARY_REFRESH_STEP = 4


def _clean_title(value: str | None, fallback: str = "Nueva conversación") -> str:
    clean = " ".join(str(value or "").split())
    return (clean or fallback)[:180]


def conversation_to_dict(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "context_type": conversation.context_type,
        "subject_id": conversation.subject_id,
        "document_id": conversation.document_id,
        "summary_available": bool(conversation.summary),
        "message_count": len(conversation.messages),
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def message_to_dict(message: ConversationMessage) -> dict:
    try:
        sources = json.loads(message.sources_json) if message.sources_json else []
    except json.JSONDecodeError:
        sources = []
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": sources,
        "created_at": message.created_at.isoformat(),
    }


def create_conversation(
    *,
    conversation_id: str | None = None,
    title: str | None = None,
    subject_id: int | None = None,
    document_id: int | None = None,
    context_type: str | None = None,
) -> dict:
    clean_id = str(conversation_id or "").strip() or create_conversation_id()
    if len(clean_id) > 80:
        raise ValueError("El identificador de conversación no es válido")

    with SessionLocal() as session:
        existing = session.get(Conversation, clean_id)
        if existing is not None:
            return conversation_to_dict(existing)

        if subject_id is not None and session.get(Subject, subject_id) is None:
            raise ValueError("La asignatura indicada no existe")
        document = session.get(Document, document_id) if document_id is not None else None
        if document_id is not None and document is None:
            raise ValueError("El material indicado no existe")
        if document is not None:
            if subject_id is not None and document.subject_id != subject_id:
                raise ValueError("El material no pertenece a la asignatura indicada")
            subject_id = document.subject_id

        effective_context = context_type or (
            "document" if document_id is not None else "subject" if subject_id is not None else "general"
        )
        if effective_context not in {"general", "subject", "document", "work_session"}:
            raise ValueError("El tipo de contexto no es válido")

        conversation = Conversation(
            id=clean_id,
            title=_clean_title(title),
            context_type=effective_context,
            subject_id=subject_id,
            document_id=document_id,
        )
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return conversation_to_dict(conversation)


def ensure_conversation(
    *,
    conversation_id: str | None,
    first_message: str,
    subject_id: int | None = None,
    document_id: int | None = None,
    context_type: str | None = None,
) -> dict:
    clean_id = str(conversation_id or "").strip()
    with SessionLocal() as session:
        existing = session.get(Conversation, clean_id) if clean_id else None
        if existing is not None:
            if document_id is not None:
                document = session.get(Document, document_id)
                if document is None:
                    raise ValueError("El material indicado no existe")
                if subject_id is not None and document.subject_id != subject_id:
                    raise ValueError("El material no pertenece a la asignatura indicada")
                existing.document_id = document_id
                existing.subject_id = document.subject_id
                existing.context_type = context_type or "document"
            elif subject_id is not None:
                if session.get(Subject, subject_id) is None:
                    raise ValueError("La asignatura indicada no existe")
                existing.subject_id = subject_id
                existing.document_id = None
                existing.context_type = context_type or "subject"
            elif context_type == "general":
                existing.subject_id = None
                existing.document_id = None
                existing.context_type = "general"
            elif context_type == "work_session":
                existing.context_type = "work_session"
            existing.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(existing)
            return conversation_to_dict(existing)

    return create_conversation(
        conversation_id=clean_id or None,
        title=_clean_title(first_message, "Nueva conversación"),
        subject_id=subject_id,
        document_id=document_id,
        context_type=context_type,
    )


def list_conversations(limit: int = 40) -> list[dict]:
    safe_limit = max(1, min(100, int(limit)))
    with SessionLocal() as session:
        conversations = session.scalars(
            select(Conversation)
            .order_by(Conversation.updated_at.desc())
            .limit(safe_limit)
        ).all()
        return [conversation_to_dict(item) for item in conversations]


def get_conversation(conversation_id: str) -> dict | None:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        payload = conversation_to_dict(conversation)
        payload["messages"] = [message_to_dict(item) for item in conversation.messages]
        return payload


def append_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
) -> dict:
    if role not in {"user", "assistant"}:
        raise ValueError("El rol del mensaje no es válido")
    clean_content = str(content or "").strip()
    if not clean_content:
        raise ValueError("El mensaje no puede estar vacío")

    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError("La conversación no existe")
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=clean_content,
            sources_json=json.dumps(sources or [], ensure_ascii=False, separators=(",", ":")),
        )
        conversation.updated_at = datetime.utcnow()
        session.add(message)
        session.commit()
        session.refresh(message)
        return message_to_dict(message)


def _compact_line(message: ConversationMessage) -> str:
    role = "Usuario" if message.role == "user" else "UniCore"
    clean = " ".join(message.content.split())
    if len(clean) > 260:
        clean = clean[:257].rstrip() + "…"
    return f"- {role}: {clean}"


def refresh_summary_if_needed(conversation_id: str) -> str | None:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        messages = list(conversation.messages)
        older_count = max(0, len(messages) - RECENT_MESSAGE_LIMIT)
        if older_count <= 0:
            return conversation.summary
        if (
            conversation.summary
            and older_count - conversation.summarized_message_count < SUMMARY_REFRESH_STEP
        ):
            return conversation.summary

        lines = [_compact_line(item) for item in messages[:older_count]]
        summary = "Resumen determinista de mensajes anteriores:\n" + "\n".join(lines)
        if len(summary) > SUMMARY_CHARACTER_LIMIT:
            summary = summary[-SUMMARY_CHARACTER_LIMIT:]
            summary = "Resumen parcial de mensajes anteriores:\n" + summary.split("\n", 1)[-1]
        conversation.summary = summary
        conversation.summarized_message_count = older_count
        conversation.updated_at = datetime.utcnow()
        session.commit()
        return summary


def build_memory_context(conversation_id: str) -> dict:
    summary = refresh_summary_if_needed(conversation_id)
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError("La conversación no existe")
        recent = list(conversation.messages)[-RECENT_MESSAGE_LIMIT:]

        kept: list[ConversationMessage] = []
        used = 0
        for message in reversed(recent):
            cost = len(message.content) + 30
            if kept and used + cost > RECENT_CHARACTER_LIMIT:
                break
            kept.append(message)
            used += cost
        kept.reverse()
        return {
            "summary": summary,
            "recent_messages": [
                {"role": item.role, "content": item.content}
                for item in kept
            ],
            "recent_message_count": len(kept),
            "recent_characters": used,
        }


def delete_conversation(conversation_id: str) -> bool:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return False
        session.delete(conversation)
        session.commit()
        return True


def clear_conversation_memory() -> int:
    """Borra únicamente memoria conversacional mediante una interfaz reusable."""

    with SessionLocal() as session:
        count = len(session.scalars(select(Conversation.id)).all())
        session.execute(delete(ConversationMessage))
        session.execute(delete(Conversation))
        session.commit()
        return count
