from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select

from src.database.connection import SessionLocal
from src.database.models import (
    CurriculumChunkReference,
    CurriculumConceptLink,
    CurriculumDocumentReference,
    CurriculumItem,
    Document,
    DocumentChunk,
    GlobalConcept,
    KnowledgeConcept,
    KnowledgeConnection,
    ReviewItem,
    StudySession,
    Subject,
)


_SOURCE_LINE = re.compile(r"^---\s*(?:Página|Diapositiva|Tabla)\s+\d+\s*---$", re.IGNORECASE)
_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NUMBERED_HEADING = re.compile(r"^(\d+\.\d+(?:\.\d+)?|\d+[.)])\s+[-–—:]?\s*(.+?)\s*$")
_UNIT_HEADING = re.compile(
    r"^(?:unit|unidad|chapter|cap[ií]tulo|lecture|lecci[oó]n|week|semana)\s*[\w.-]*\s*[-–—:]?\s*(.+?)\s*$",
    re.IGNORECASE,
)
_DECIMAL_UNIT_HEADING = re.compile(
    r"^(?:unit|unidad|chapter|cap[ií]tulo|lecture|lecci[oó]n|week|semana)\s*\d+\.\d+",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = {"and", "the", "of", "de", "del", "la", "las", "los", "y", "el", "a", "an"}
_RANK = {"unit": 1, "topic": 2, "subtopic": 3}


@dataclass
class CurriculumCandidate:
    item_type: str
    name: str
    start: int
    end: int
    parent_index: int | None
    position: int
    source_label: str | None = None


def normalize_curriculum_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(character for character in normalized if not unicodedata.combining(character))
    tokens = []
    for token in _WORD.findall(ascii_value):
        if token in _STOPWORDS:
            continue
        if len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        tokens.append(token)
    return " ".join(tokens)


def _tokens(value: str) -> set[str]:
    return set(normalize_curriculum_name(value).split())


def curriculum_name_similarity(first: str, second: str) -> float:
    first_tokens, second_tokens = _tokens(first), _tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0
    if first_tokens == second_tokens:
        return 1.0
    overlap = first_tokens & second_tokens
    union = first_tokens | second_tokens
    score = len(overlap) / len(union)
    if min(len(first_tokens), len(second_tokens)) >= 2 and score >= 2 / 3:
        return score
    return 0.0


def _looks_like_plain_heading(line: str, next_line: str | None, previous_was_source: bool) -> bool:
    clean = line.strip().rstrip(":")
    words = clean.split()
    if not 2 <= len(words) <= 12 or len(clean) > 110:
        return False
    if clean.endswith((".", "?", "!", ";")):
        return False
    letters = [word for word in words if any(character.isalpha() for character in word)]
    title_words = sum(word[:1].isupper() for word in letters)
    uppercase = clean.isupper() and len(clean) > 4
    followed_by_body = bool(next_line and len(next_line.strip()) > max(55, len(clean) * 1.35))
    return previous_was_source or uppercase or (bool(letters) and title_words / len(letters) >= 0.7 and followed_by_body)


def extract_curriculum_candidates(text: str, document_title: str) -> list[CurriculumCandidate]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)

    raw: list[tuple[str, str, int, str | None]] = []
    current_source: str | None = None
    previous_was_source = False
    current_unit_seen = False
    current_topic_seen = False

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            previous_was_source = False
            continue
        if _SOURCE_LINE.match(line):
            current_source = line.strip("- ")
            previous_was_source = True
            continue
        next_line = next((item.strip() for item in lines[index + 1:] if item.strip()), None)
        markdown = _MARKDOWN_HEADING.match(line)
        numbered = _NUMBERED_HEADING.match(line)
        explicit_unit = _UNIT_HEADING.match(line)
        item_type: str | None = None
        name = line

        if explicit_unit:
            item_type = "topic" if current_unit_seen and _DECIMAL_UNIT_HEADING.match(line) else "unit"
            name = line.rstrip(":")
        elif numbered:
            number = numbered.group(1).rstrip(".)")
            depth = number.count(".") + 1
            # A simple ``1.``/``1)`` inside an explicit unit is normally an
            # enumerated topic, not a new top-level unit.  Keeping it under the
            # current unit avoids promoting slide lists to curriculum units.
            if depth == 1 and current_unit_seen:
                item_type = "topic"
            else:
                item_type = "unit" if depth == 1 else "topic" if depth == 2 else "subtopic"
            name = numbered.group(2).strip().rstrip(":")
        elif markdown:
            level = len(markdown.group(1))
            name = markdown.group(2).strip().rstrip("# ").rstrip(":")
            if _UNIT_HEADING.match(name):
                item_type = "unit"
            elif level == 1:
                item_type = "topic"
            elif level == 2:
                item_type = "topic" if current_unit_seen and not current_topic_seen else "subtopic"
            else:
                item_type = "subtopic"
        elif _looks_like_plain_heading(line, next_line, previous_was_source):
            item_type, name = "topic", line.rstrip(":")

        previous_was_source = False
        name = " ".join(name.split())
        if item_type is None or len(normalize_curriculum_name(name)) < 2:
            continue
        raw.append((item_type, name, offsets[index], current_source))
        if item_type == "unit":
            current_unit_seen, current_topic_seen = True, False
        elif item_type == "topic":
            current_topic_seen = True

    if not raw:
        return []

    candidates: list[CurriculumCandidate] = []
    current_unit: int | None = None
    current_topic: int | None = None
    synthetic_unit: int | None = None
    positions = {"unit": 0, "topic": 0, "subtopic": 0}

    for raw_index, (item_type, name, start, source_label) in enumerate(raw):
        if item_type != "unit" and current_unit is None:
            if synthetic_unit is None:
                positions["unit"] += 1
                synthetic_unit = len(candidates)
                candidates.append(CurriculumCandidate(
                    item_type="unit",
                    name=f"Material · {Path(document_title).stem}",
                    start=0,
                    end=len(text),
                    parent_index=None,
                    position=positions["unit"],
                ))
            current_unit = synthetic_unit
        positions[item_type] += 1
        parent_index = None
        if item_type == "topic":
            parent_index = current_unit
        elif item_type == "subtopic":
            parent_index = current_topic
            if parent_index is None:
                item_type = "topic"
                parent_index = current_unit
        candidate_index = len(candidates)
        candidates.append(CurriculumCandidate(
            item_type=item_type,
            name=name,
            start=start,
            end=len(text),
            parent_index=parent_index,
            position=positions[item_type],
            source_label=source_label,
        ))
        if item_type == "unit":
            current_unit, current_topic = candidate_index, None
        elif item_type == "topic":
            current_topic = candidate_index

    for index, candidate in enumerate(candidates):
        if synthetic_unit is not None and candidate is candidates[synthetic_unit]:
            continue
        for later in candidates[index + 1:]:
            if later.start > candidate.start and _RANK[later.item_type] <= _RANK[candidate.item_type]:
                candidate.end = later.start
                break
    return candidates


def _find_equivalent_item(session, *, subject_id: int, item_type: str, name: str) -> CurriculumItem | None:
    exact = session.scalar(select(CurriculumItem).where(
        CurriculumItem.subject_id == subject_id,
        CurriculumItem.item_type == item_type,
        CurriculumItem.normalized_name == normalize_curriculum_name(name),
    ))
    if exact is not None:
        return exact
    if item_type == "unit":
        return None
    candidates = session.scalars(select(CurriculumItem).where(
        CurriculumItem.subject_id == subject_id,
        CurriculumItem.item_type == item_type,
    )).all()
    scored = [(curriculum_name_similarity(name, item.name), item) for item in candidates]
    score, item = max(scored, default=(0.0, None), key=lambda pair: pair[0])
    return item if score >= 2 / 3 else None


def _add_connection(session, first_id: int, second_id: int, relationship: str, evidence: str) -> None:
    if first_id == second_id:
        return
    source_id, target_id = sorted((first_id, second_id))
    existing = session.scalar(select(KnowledgeConnection).where(
        KnowledgeConnection.source_concept_id == source_id,
        KnowledgeConnection.target_concept_id == target_id,
    ))
    if existing is None:
        session.add(KnowledgeConnection(
            source_concept_id=source_id,
            target_concept_id=target_id,
            relationship=relationship,
            source_type="curriculum",
            evidence_reference=evidence,
        ))
    elif relationship == "equivalent" and existing.source_type != "manual":
        existing.relationship = "equivalent"
        existing.evidence_reference = evidence


def _ensure_knowledge_concept(session, item: CurriculumItem, document_title: str) -> KnowledgeConcept:
    concept = session.scalar(select(KnowledgeConcept).where(
        KnowledgeConcept.subject_id == item.subject_id,
        KnowledgeConcept.normalized_name == item.normalized_name,
    ))
    if concept is None:
        concept = KnowledgeConcept(
            subject_id=item.subject_id,
            name=item.name,
            normalized_name=item.normalized_name,
            status="unassessed",
            evidence_count=0,
            assessed_evidence_count=0,
            exposure_minutes=0,
        )
        session.add(concept)
        session.flush()

    global_concept = session.scalar(select(GlobalConcept).where(
        GlobalConcept.normalized_name == item.normalized_name,
    ))
    if global_concept is None:
        global_concept = GlobalConcept(
            name=item.name,
            normalized_name=item.normalized_name,
            aliases_json=json.dumps([item.name], ensure_ascii=False),
            source="automatic",
        )
        session.add(global_concept)
        session.flush()
    concept.global_concept_id = global_concept.id

    linked = session.scalar(select(CurriculumConceptLink).where(
        CurriculumConceptLink.curriculum_item_id == item.id,
        CurriculumConceptLink.knowledge_concept_id == concept.id,
    ))
    if linked is None:
        session.add(CurriculumConceptLink(curriculum_item_id=item.id, knowledge_concept_id=concept.id))

    equivalents = session.scalars(select(KnowledgeConcept).where(
        KnowledgeConcept.global_concept_id == global_concept.id,
        KnowledgeConcept.subject_id != item.subject_id,
    )).all()
    for other in equivalents:
        _add_connection(session, concept.id, other.id, "equivalent", f"Coincidencia curricular: {document_title}")

    other_subject_concepts = session.scalars(select(KnowledgeConcept).where(
        KnowledgeConcept.subject_id != item.subject_id,
        KnowledgeConcept.global_concept_id != global_concept.id,
    )).all()
    for other in other_subject_concepts:
        first, second = _tokens(item.name), _tokens(other.name)
        overlap = first & second
        if len(overlap) >= 2 and len(overlap) / len(first | second) >= 0.6:
            _add_connection(session, concept.id, other.id, "related", f"Solapamiento curricular: {document_title}")
    return concept


def build_curriculum_for_document(document_id: int, *, session_factory=SessionLocal, force: bool = False) -> dict[str, Any]:
    with session_factory() as session:
        document = session.get(Document, document_id)
        if document is None or document.subject_id is None:
            return {"ok": False, "error": "El documento no pertenece a una asignatura"}
        if document.curriculum_processed_at is not None and not force:
            return {"ok": True, "processed": False, "reason": "already_processed", "document_id": document_id}
        candidates = extract_curriculum_candidates(document.extracted_text or "", document.title)
        chunks = session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all()
        document_reference_item_ids = set(session.scalars(select(CurriculumDocumentReference.curriculum_item_id).where(
            CurriculumDocumentReference.document_id == document.id,
        )))
        chunk_reference_keys = set(session.execute(
            select(CurriculumChunkReference.curriculum_item_id, CurriculumChunkReference.chunk_id)
            .join(DocumentChunk, DocumentChunk.id == CurriculumChunkReference.chunk_id)
            .where(DocumentChunk.document_id == document.id)
        ).all())
        persisted: list[CurriculumItem] = []

        for candidate in candidates:
            parent = persisted[candidate.parent_index] if candidate.parent_index is not None else None
            item = _find_equivalent_item(
                session,
                subject_id=document.subject_id,
                item_type=candidate.item_type,
                name=candidate.name,
            )
            if item is None:
                item = CurriculumItem(
                    subject_id=document.subject_id,
                    parent_id=parent.id if parent else None,
                    item_type=candidate.item_type,
                    name=candidate.name,
                    normalized_name=normalize_curriculum_name(candidate.name),
                    position=candidate.position,
                    source="automatic",
                )
                session.add(item)
                session.flush()
            elif not item.manually_locked and item.parent_id is None and parent is not None:
                item.parent_id = parent.id
            persisted.append(item)

            if item.id not in document_reference_item_ids:
                session.add(CurriculumDocumentReference(
                    curriculum_item_id=item.id,
                    document_id=document.id,
                    source_label=candidate.source_label,
                ))
                document_reference_item_ids.add(item.id)

            for chunk in chunks:
                overlaps = chunk.char_end > candidate.start and chunk.char_start < candidate.end
                if not overlaps:
                    continue
                reference_key = (item.id, chunk.id)
                if reference_key not in chunk_reference_keys:
                    session.add(CurriculumChunkReference(curriculum_item_id=item.id, chunk_id=chunk.id))
                    chunk_reference_keys.add(reference_key)

            if item.item_type in {"topic", "subtopic"}:
                _ensure_knowledge_concept(session, item, document.title)

            # SessionLocal deliberately disables autoflush.  Persist each
            # candidate's references before an equivalent heading can reuse
            # the same item later in the document.
            session.flush()

        document.curriculum_processed_at = datetime.utcnow()
        session.commit()
        return {
            "ok": True,
            "processed": True,
            "document_id": document.id,
            "candidate_count": len(candidates),
            "item_count": len({item.id for item in persisted}),
        }


def backfill_pending_curriculum(*, session_factory=SessionLocal) -> dict[str, int]:
    with session_factory() as session:
        pending_ids = list(session.scalars(select(Document.id).where(
            Document.subject_id.is_not(None),
            Document.extracted_text.is_not(None),
            Document.curriculum_processed_at.is_(None),
        )))
    processed = failed = 0
    for document_id in pending_ids:
        try:
            result = build_curriculum_for_document(document_id, session_factory=session_factory)
            processed += int(bool(result.get("ok")))
            failed += int(not result.get("ok"))
        except Exception:
            failed += 1
    return {"processed": processed, "failed": failed}


def _item_status(item: CurriculumItem, concept: KnowledgeConcept | None, reviews: list[ReviewItem], studied_names: set[str]) -> str:
    matching_reviews = [review for review in reviews if normalize_curriculum_name(review.concept_name or review.topic) == item.normalized_name]
    best_box = max((review.leitner_box for review in matching_reviews), default=0)
    if best_box >= 4 or concept and concept.status in {"strong", "mastered"}:
        return "mastered"
    if best_box == 3 or concept and concept.status in {"developing", "consolidating"}:
        return "consolidating"
    if best_box or item.normalized_name in studied_names or concept and concept.evidence_count > 0:
        return "learning"
    return "not_studied"


def curriculum_for_subject(subject_id: int, *, session_factory=SessionLocal) -> dict[str, Any]:
    with session_factory() as session:
        subject = session.get(Subject, subject_id)
        if subject is None:
            return {"ok": False, "error": "La asignatura no existe"}
        items = list(session.scalars(select(CurriculumItem).where(
            CurriculumItem.subject_id == subject_id,
        ).order_by(CurriculumItem.position, CurriculumItem.id)))
        item_ids = [item.id for item in items]
        document_refs = list(session.scalars(select(CurriculumDocumentReference).where(
            CurriculumDocumentReference.curriculum_item_id.in_(item_ids)
        ))) if item_ids else []
        documents = {item.id: item for item in session.scalars(select(Document).where(
            Document.id.in_([reference.document_id for reference in document_refs])
        ))} if document_refs else {}
        links = list(session.scalars(select(CurriculumConceptLink).where(
            CurriculumConceptLink.curriculum_item_id.in_(item_ids)
        ))) if item_ids else []
        concepts = {item.id: item for item in session.scalars(select(KnowledgeConcept).where(
            KnowledgeConcept.id.in_([link.knowledge_concept_id for link in links])
        ))} if links else {}
        concept_by_item = {link.curriculum_item_id: concepts.get(link.knowledge_concept_id) for link in links}
        reviews = list(session.scalars(select(ReviewItem).where(ReviewItem.subject_id == subject_id)))
        studied_names = {
            normalize_curriculum_name(value)
            for value in session.scalars(select(StudySession.topic).where(
                StudySession.subject_id == subject_id,
                StudySession.topic.is_not(None),
            ))
            if value
        }
        subjects = {item.id: item.name for item in session.scalars(select(Subject))}
        global_occurrences: dict[int, list[dict[str, Any]]] = {}
        global_ids = {concept.global_concept_id for concept in concepts.values() if concept and concept.global_concept_id}
        if global_ids:
            for occurrence in session.scalars(select(KnowledgeConcept).where(
                KnowledgeConcept.global_concept_id.in_(global_ids),
                KnowledgeConcept.subject_id != subject_id,
            )):
                global_occurrences.setdefault(occurrence.global_concept_id, []).append({
                    "subject_id": occurrence.subject_id,
                    "subject_name": subjects.get(occurrence.subject_id, "Asignatura"),
                    "concept_name": occurrence.name,
                })

        children: dict[int | None, list[CurriculumItem]] = {}
        for item in items:
            children.setdefault(item.parent_id, []).append(item)

        def sources_for(item_id: int) -> list[dict[str, Any]]:
            result = []
            for reference in document_refs:
                if reference.curriculum_item_id != item_id or reference.document_id not in documents:
                    continue
                document = documents[reference.document_id]
                result.append({
                    "document_id": document.id,
                    "title": document.title,
                    "file_type": document.file_type,
                    "source_label": reference.source_label,
                })
            return result

        def serialize(item: CurriculumItem) -> dict[str, Any]:
            concept = concept_by_item.get(item.id)
            also_seen = global_occurrences.get(concept.global_concept_id, []) if concept and concept.global_concept_id else []
            return {
                "id": item.id,
                "name": item.name,
                "type": item.item_type,
                "source": item.source,
                "manually_locked": item.manually_locked,
                "status": _item_status(item, concept, reviews, studied_names),
                "sources": sources_for(item.id),
                "also_seen_in": also_seen,
            }

        units = []
        for unit in children.get(None, []):
            topics = []
            for topic in children.get(unit.id, []):
                topic_data = serialize(topic)
                topic_data["subtopics"] = [serialize(item) for item in children.get(topic.id, [])]
                topics.append(topic_data)
            worked = sum(item["status"] != "not_studied" for item in topics)
            units.append({
                **serialize(unit),
                "topics": topics,
                "topic_count": len(topics),
                "worked_topic_count": worked,
            })
        pending_documents = session.scalar(select(func.count(Document.id)).where(
            Document.subject_id == subject_id,
            Document.extracted_text.is_not(None),
            Document.curriculum_processed_at.is_(None),
        )) or 0
        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "academic_language": subject.academic_language,
                "academic_language_configured": subject.academic_language_configured,
            },
            "units": units,
            "item_count": len(items),
            "pending_document_count": int(pending_documents),
        }


def curriculum_scope(subject_id: int, item_id: int, *, session_factory=SessionLocal) -> dict[str, Any]:
    with session_factory() as session:
        item = session.get(CurriculumItem, item_id)
        if item is None or item.subject_id != subject_id or item.item_type not in {"topic", "subtopic"}:
            return {"ok": False, "error": "El tema curricular no está disponible"}
        scope_ids = [item.id]
        if item.item_type == "topic":
            scope_ids.extend(session.scalars(select(CurriculumItem.id).where(CurriculumItem.parent_id == item.id)))
        chunk_ids = list(session.scalars(select(CurriculumChunkReference.chunk_id).where(
            CurriculumChunkReference.curriculum_item_id.in_(scope_ids)
        ).distinct()))
        document_ids = list(session.scalars(select(CurriculumDocumentReference.document_id).where(
            CurriculumDocumentReference.curriculum_item_id.in_(scope_ids)
        ).distinct()))
        return {
            "ok": True,
            "item_id": item.id,
            "item_type": item.item_type,
            "topic": item.name,
            "chunk_ids": chunk_ids,
            "document_ids": document_ids,
        }
