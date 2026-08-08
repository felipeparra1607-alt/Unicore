import json
import re
import unicodedata

from datetime import (
    datetime,
    time,
)

from sqlalchemy import (
    select,
)

from src.database.connection import (
    SessionLocal,
)

from src.database.models import (
    KnowledgeConcept,
    KnowledgeEvidence,
    ReviewItem,
    StudyAttempt,
    StudySession,
    Subject,
)


def normalize_concept_name(
    value: str,
) -> str:
    """
    Normaliza nombres para evitar conceptos duplicados
    por mayúsculas, acentos o espacios.

    Ejemplo:
    "  Ventaja Competitiva "
    → "ventaja competitiva"
    """

    clean = (
        value
        .strip()
        .casefold()
    )

    clean = unicodedata.normalize(
        "NFKD",
        clean,
    )

    clean = "".join(
        character
        for character in clean
        if not unicodedata.combining(
            character
        )
    )

    clean = re.sub(
        r"\s+",
        " ",
        clean,
    )

    return clean


def clean_concept_display_name(
    value: str,
) -> str:
    """
    Conserva un nombre agradable para mostrar.
    """

    return re.sub(
        r"\s+",
        " ",
        value.strip(),
    )


def mastery_status(
    mastery_percentage: float | None,
) -> str:
    """
    Convierte la puntuación de dominio en
    un estado fácil de utilizar.

    Estos límites son internos y podremos
    calibrarlos posteriormente con evals.
    """

    if mastery_percentage is None:
        return "unassessed"

    if mastery_percentage >= 80:
        return "strong"

    if mastery_percentage >= 60:
        return "developing"

    return "weak"


def review_mastery_score(
    item: ReviewItem,
) -> float:
    """
    Convierte el estado del repaso en una
    señal aproximada de dominio.

    No pretende ser una nota académica.
    """

    if item.correct_streak >= 4:
        return 92.0

    if item.correct_streak == 3:
        return 84.0

    if item.correct_streak == 2:
        return 72.0

    if item.correct_streak == 1:
        return 58.0

    if item.incorrect_count >= 3:
        return 20.0

    if item.incorrect_count >= 2:
        return 28.0

    return 35.0


def concept_to_dict(
    concept: KnowledgeConcept,
) -> dict:
    """
    Serializa un concepto sin cargar
    sus evidencias completas.
    """

    return {
        "id": concept.id,
        "subject_id": concept.subject_id,
        "name": concept.name,
        "mastery_percentage": (
            round(
                concept.mastery_percentage,
                2,
            )
            if (
                concept.mastery_percentage
                is not None
            )
            else None
        ),
        "status": concept.status,
        "evidence_count": (
            concept.evidence_count
        ),
        "assessed_evidence_count": (
            concept.assessed_evidence_count
        ),
        "exposure_minutes": (
            concept.exposure_minutes
        ),
        "last_evidence_at": (
            concept.last_evidence_at.isoformat()
            if concept.last_evidence_at
            else None
        ),
    }


def get_or_create_concept(
    session,
    subject_id: int,
    topic: str,
) -> KnowledgeConcept | None:
    """
    Obtiene o crea un concepto usando el topic
    disponible en los datos académicos.
    """

    display_name = (
        clean_concept_display_name(
            topic
        )
    )

    normalized_name = (
        normalize_concept_name(
            topic
        )
    )

    if not normalized_name:
        return None

    concept = session.scalar(
        select(
            KnowledgeConcept
        ).where(
            KnowledgeConcept.subject_id
            == subject_id,
            KnowledgeConcept.normalized_name
            == normalized_name,
        )
    )

    if concept is not None:
        return concept

    concept = KnowledgeConcept(
        subject_id=subject_id,
        name=display_name,
        normalized_name=normalized_name,
        status="unassessed",
        evidence_count=0,
        assessed_evidence_count=0,
        exposure_minutes=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    session.add(
        concept
    )

    session.flush()

    return concept


def upsert_evidence(
    session,
    concept: KnowledgeConcept,
    source_type: str,
    source_id: int,
    observed_at: datetime,
    evidence_score: float | None = None,
    weight: float = 1.0,
    exposure_minutes: int = 0,
) -> tuple[
    KnowledgeEvidence,
    bool,
]:
    """
    Crea o actualiza una evidencia.

    La combinación:
    concept + source_type + source_id
    es única, así que sincronizar varias veces
    no crea duplicados.
    """

    evidence = session.scalar(
        select(
            KnowledgeEvidence
        ).where(
            KnowledgeEvidence.concept_id
            == concept.id,
            KnowledgeEvidence.source_type
            == source_type,
            KnowledgeEvidence.source_id
            == source_id,
        )
    )

    created = False

    if evidence is None:
        evidence = KnowledgeEvidence(
            concept_id=concept.id,
            subject_id=concept.subject_id,
            source_type=source_type,
            source_id=source_id,
            created_at=datetime.utcnow(),
        )

        session.add(
            evidence
        )

        created = True

    evidence.evidence_score = (
        evidence_score
    )

    evidence.weight = weight

    evidence.exposure_minutes = max(
        0,
        exposure_minutes,
    )

    evidence.observed_at = (
        observed_at
    )

    evidence.updated_at = (
        datetime.utcnow()
    )

    return evidence, created


def recalculate_concept(
    session,
    concept: KnowledgeConcept,
) -> None:
    """
    Recalcula el dominio consolidado de un concepto.
    """

    evidence_items = session.scalars(
        select(
            KnowledgeEvidence
        ).where(
            KnowledgeEvidence.concept_id
            == concept.id
        )
    ).all()

    assessed = [
        evidence
        for evidence in evidence_items
        if (
            evidence.evidence_score
            is not None
            and evidence.weight > 0
        )
    ]

    weighted_total = sum(
        evidence.evidence_score
        * evidence.weight
        for evidence in assessed
    )

    weight_total = sum(
        evidence.weight
        for evidence in assessed
    )

    mastery = None

    if weight_total > 0:
        mastery = (
            weighted_total
            / weight_total
        )

        mastery = max(
            0.0,
            min(
                100.0,
                mastery,
            ),
        )

    exposure_minutes = sum(
        evidence.exposure_minutes
        for evidence in evidence_items
    )

    observed_dates = [
        evidence.observed_at
        for evidence in evidence_items
        if evidence.observed_at
        is not None
    ]

    concept.mastery_percentage = (
        round(
            mastery,
            2,
        )
        if mastery is not None
        else None
    )

    concept.status = mastery_status(
        mastery
    )

    concept.evidence_count = len(
        evidence_items
    )

    concept.assessed_evidence_count = (
        len(assessed)
    )

    concept.exposure_minutes = (
        exposure_minutes
    )

    concept.last_evidence_at = (
        max(observed_dates)
        if observed_dates
        else None
    )

    concept.updated_at = (
        datetime.utcnow()
    )


def sync_subject_knowledge_map(
    subject_id: int,
) -> dict:
    """
    Sincroniza el Knowledge Map de una asignatura.

    Fuentes actuales:

    1. quizzes completados
       → evidencia evaluada

    2. repaso espaciado
       → evidencia evaluada

    3. sesiones de estudio
       → exposición, NO dominio

    No utiliza IA.
    """

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

        affected_concept_ids: set[int] = set()

        created_evidence_count = 0
        updated_evidence_count = 0

        # ====================================================
        # QUIZZES
        # ====================================================

        attempts = session.scalars(
            select(
                StudyAttempt
            ).where(
                StudyAttempt.subject_id
                == subject_id,
                StudyAttempt.status
                == "completed",
            )
        ).all()

        for attempt in attempts:
            if not attempt.topic:
                continue

            if (
                attempt.score_percentage
                is None
            ):
                continue

            concept = get_or_create_concept(
                session,
                subject_id,
                attempt.topic,
            )

            if concept is None:
                continue

            observed_at = (
                attempt.completed_at
                or attempt.started_at
                or datetime.utcnow()
            )

            _, created = upsert_evidence(
                session=session,
                concept=concept,
                source_type="quiz_attempt",
                source_id=attempt.id,
                evidence_score=float(
                    attempt.score_percentage
                ),
                weight=1.0,
                exposure_minutes=0,
                observed_at=observed_at,
            )

            affected_concept_ids.add(
                concept.id
            )

            if created:
                created_evidence_count += 1
            else:
                updated_evidence_count += 1

        # ====================================================
        # REPASO
        # ====================================================

        review_items = session.scalars(
            select(
                ReviewItem
            ).where(
                ReviewItem.subject_id
                == subject_id
            )
        ).all()

        for item in review_items:
            if not item.topic:
                continue

            concept = get_or_create_concept(
                session,
                subject_id,
                item.topic,
            )

            if concept is None:
                continue

            observed_at = (
                item.last_reviewed_at
                or item.updated_at
                or item.created_at
                or datetime.utcnow()
            )

            score = review_mastery_score(
                item
            )

            _, created = upsert_evidence(
                session=session,
                concept=concept,
                source_type="review_item",
                source_id=item.id,
                evidence_score=score,
                weight=0.75,
                exposure_minutes=0,
                observed_at=observed_at,
            )

            affected_concept_ids.add(
                concept.id
            )

            if created:
                created_evidence_count += 1
            else:
                updated_evidence_count += 1

        # ====================================================
        # SESIONES DE ESTUDIO
        # ====================================================

        study_sessions = session.scalars(
            select(
                StudySession
            ).where(
                StudySession.subject_id
                == subject_id
            )
        ).all()

        for study_session in study_sessions:
            if not study_session.topic:
                continue

            concept = get_or_create_concept(
                session,
                subject_id,
                study_session.topic,
            )

            if concept is None:
                continue

            observed_at = (
                study_session.completed_at
                or study_session.started_at
            )

            if observed_at is None:
                observed_at = datetime.combine(
                    study_session.session_date,
                    time.min,
                )

            _, created = upsert_evidence(
                session=session,
                concept=concept,
                source_type="study_session",
                source_id=study_session.id,
                evidence_score=None,
                weight=0.0,
                exposure_minutes=(
                    study_session.duration_minutes
                ),
                observed_at=observed_at,
            )

            affected_concept_ids.add(
                concept.id
            )

            if created:
                created_evidence_count += 1
            else:
                updated_evidence_count += 1

        session.flush()

        concepts = session.scalars(
            select(
                KnowledgeConcept
            ).where(
                KnowledgeConcept.subject_id
                == subject_id
            )
        ).all()

        for concept in concepts:
            recalculate_concept(
                session,
                concept,
            )

        session.commit()

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            },
            "concept_count": len(
                concepts
            ),
            "created_evidence_count": (
                created_evidence_count
            ),
            "updated_evidence_count": (
                updated_evidence_count
            ),
            "cost": {
                "ai_used": False,
                "estimated_cost": 0,
            },
        }


def sync_knowledge_map(
    subject_id: int | None = None,
) -> dict:
    """
    Sincroniza una asignatura o todas.
    """

    if subject_id is not None:
        return sync_subject_knowledge_map(
            subject_id
        )

    with SessionLocal() as session:
        subject_ids = session.scalars(
            select(
                Subject.id
            ).order_by(
                Subject.id
            )
        ).all()

    results = []

    for current_subject_id in subject_ids:
        result = (
            sync_subject_knowledge_map(
                current_subject_id
            )
        )

        results.append(
            result
        )

    return {
        "ok": all(
            result.get("ok")
            for result in results
        ),
        "subject_count": len(
            results
        ),
        "results": results,
        "cost": {
            "ai_used": False,
            "estimated_cost": 0,
        },
    }


def build_subject_knowledge_map(
    subject_id: int,
) -> dict:
    """
    Construye el Resource compacto del
    Knowledge Map.
    """

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

        concepts = session.scalars(
            select(
                KnowledgeConcept
            )
            .where(
                KnowledgeConcept.subject_id
                == subject_id
            )
            .order_by(
                KnowledgeConcept.mastery_percentage
                .asc()
                .nulls_last(),
                KnowledgeConcept.name.asc(),
            )
        ).all()

        strong = [
            concept
            for concept in concepts
            if concept.status
            == "strong"
        ]

        developing = [
            concept
            for concept in concepts
            if concept.status
            == "developing"
        ]

        weak = [
            concept
            for concept in concepts
            if concept.status
            == "weak"
        ]

        unassessed = [
            concept
            for concept in concepts
            if concept.status
            == "unassessed"
        ]

        assessed_mastery = [
            concept.mastery_percentage
            for concept in concepts
            if (
                concept.mastery_percentage
                is not None
            )
        ]

        overall_mastery = None

        if assessed_mastery:
            overall_mastery = round(
                sum(
                    assessed_mastery
                )
                / len(
                    assessed_mastery
                ),
                2,
            )

        return {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
            },
            "summary": {
                "concept_count": len(
                    concepts
                ),
                "assessed_concept_count": (
                    len(concepts)
                    - len(unassessed)
                ),
                "overall_mastery_percentage": (
                    overall_mastery
                ),
                "strong_count": len(
                    strong
                ),
                "developing_count": len(
                    developing
                ),
                "weak_count": len(
                    weak
                ),
                "unassessed_count": len(
                    unassessed
                ),
            },
            "priority_concepts": [
                concept_to_dict(
                    concept
                )
                for concept in (
                    weak
                    + developing
                    + unassessed
                )[:10]
            ],
            "concepts": [
                concept_to_dict(
                    concept
                )
                for concept in concepts
            ],
            "interpretation": {
                "strong": (
                    "80-100: evidencia de dominio fuerte"
                ),
                "developing": (
                    "60-79.99: dominio en desarrollo"
                ),
                "weak": (
                    "0-59.99: necesita atención"
                ),
                "unassessed": (
                    "Hay exposición pero no suficiente "
                    "evidencia evaluada"
                ),
            },
        }


def register_knowledge_map(
    mcp,
) -> None:
    """
    Expone únicamente:

    - 1 Tool que modifica/sincroniza estado.
    - 1 Resource de lectura.
    """

    @mcp.tool()
    def sync_knowledge_map_tool(
        subject_id: int | None = None,
    ) -> dict:
        """
        Sincroniza el Knowledge Map usando quizzes,
        repasos y sesiones existentes.

        Coste de IA: 0.
        """

        return sync_knowledge_map(
            subject_id=subject_id
        )

    @mcp.resource(
        (
            "unicore://subjects/"
            "{subject_id}/knowledge"
        )
    )
    def subject_knowledge_resource(
        subject_id: int,
    ) -> str:
        """
        Devuelve conceptos, dominio, fortalezas
        y debilidades de una asignatura.
        """

        return json.dumps(
            build_subject_knowledge_map(
                subject_id
            ),
            ensure_ascii=False,
            indent=2,
            default=str,
        )