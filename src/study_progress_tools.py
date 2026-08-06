import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.database.connection import SessionLocal
from src.database.models import (
    StudyAnswer,
    StudyAttempt,
    Subject,
)


def parse_json_object(
    value: str | dict[str, Any],
) -> dict[str, Any]:
    """Convierte texto JSON o diccionario en un diccionario."""

    if isinstance(value, dict):
        return value

    if not isinstance(value, str):
        raise ValueError(
            "El quiz debe ser un objeto o un texto JSON"
        )

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(
            "El quiz no contiene JSON válido"
        ) from error

    if not isinstance(parsed, dict):
        raise ValueError(
            "El quiz debe ser un objeto JSON"
        )

    return parsed


def validate_quiz_items(
    quiz_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Valida un quiz generado por UniCore."""

    items = quiz_data.get("items")

    if not isinstance(items, list) or not items:
        raise ValueError(
            "El quiz debe contener una lista items"
        )

    validated_items = []

    for index, item in enumerate(
        items,
        start=1,
    ):
        if not isinstance(item, dict):
            raise ValueError(
                f"La pregunta {index} no es válida"
            )

        question = item.get("question")
        options = item.get("options")
        correct_index = item.get(
            "correct_index"
        )

        if not isinstance(question, str):
            raise ValueError(
                f"Falta question en la pregunta {index}"
            )

        if (
            not isinstance(options, list)
            or len(options) != 4
            or not all(
                isinstance(option, str)
                for option in options
            )
        ):
            raise ValueError(
                f"La pregunta {index} debe tener "
                "exactamente cuatro opciones"
            )

        if correct_index not in {
            0,
            1,
            2,
            3,
        }:
            raise ValueError(
                f"correct_index inválido "
                f"en la pregunta {index}"
            )

        validated_items.append({
            "question": question.strip(),
            "options": options,
            "correct_index": correct_index,
            "explanation": item.get(
                "explanation"
            ),
            "sources": item.get(
                "sources",
                [],
            ),
        })

    return validated_items


def attempt_to_dict(
    attempt: StudyAttempt,
    include_quiz: bool = False,
) -> dict[str, Any]:
    """Convierte un intento en un diccionario."""

    result = {
        "id": attempt.id,
        "subject_id": attempt.subject_id,
        "topic": attempt.topic,
        "study_mode": attempt.study_mode,
        "difficulty": attempt.difficulty,
        "total_questions": attempt.total_questions,
        "correct_answers": attempt.correct_answers,
        "score_percentage": (
            attempt.score_percentage
        ),
        "status": attempt.status,
        "started_at": (
            attempt.started_at.isoformat()
            if attempt.started_at
            else None
        ),
        "completed_at": (
            attempt.completed_at.isoformat()
            if attempt.completed_at
            else None
        ),
    }

    if include_quiz:
        result["quiz"] = json.loads(
            attempt.questions_json
        )

        result["submitted_answers"] = (
            json.loads(attempt.answers_json)
            if attempt.answers_json
            else None
        )

        result["results"] = (
            json.loads(attempt.results_json)
            if attempt.results_json
            else None
        )

    return result


def register_study_progress_tools(mcp) -> None:
    """Registra las herramientas de progreso de estudio."""

    @mcp.tool()
    def create_quiz_attempt(
        subject_id: int,
        topic: str,
        quiz: str | dict,
        difficulty: str = "intermedio",
    ) -> dict:
        """
        Guarda un quiz generado y crea un intento pendiente.

        En quiz debes pegar el objeto content devuelto
        por generate_study_material.
        """

        clean_topic = topic.strip()

        if not clean_topic:
            return {
                "ok": False,
                "error": (
                    "El tema no puede estar vacío"
                ),
            }

        try:
            quiz_data = parse_json_object(
                quiz
            )

            quiz_items = validate_quiz_items(
                quiz_data
            )

        except ValueError as error:
            return {
                "ok": False,
                "error": str(error),
            }

        normalized_quiz = {
            "items": quiz_items,
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

            attempt = StudyAttempt(
                subject_id=subject_id,
                topic=clean_topic,
                study_mode="quiz",
                difficulty=(
                    difficulty.strip().casefold()
                    or "intermedio"
                ),
                questions_json=json.dumps(
                    normalized_quiz,
                    ensure_ascii=False,
                ),
                total_questions=len(
                    quiz_items
                ),
                status="pending",
            )

            session.add(attempt)
            session.commit()
            session.refresh(attempt)

            public_items = []

            for index, item in enumerate(
                quiz_items
            ):
                public_items.append({
                    "question_index": index,
                    "question": item["question"],
                    "options": item["options"],
                })

            return {
                "ok": True,
                "attempt": attempt_to_dict(
                    attempt
                ),
                "questions": public_items,
                "instructions": (
                    "Responde con una lista de índices. "
                    "Cada índice debe ser 0, 1, 2 o 3."
                ),
            }

    @mcp.tool()
    def submit_quiz_attempt(
        attempt_id: int,
        selected_answers: list[int],
    ) -> dict:
        """
        Corrige un quiz.

        selected_answers debe contener una respuesta
        por pregunta. Por ejemplo: [1, 2, 0, 1, 1].
        """

        with SessionLocal() as session:
            attempt = session.get(
                StudyAttempt,
                attempt_id,
            )

            if attempt is None:
                return {
                    "ok": False,
                    "error": (
                        "El intento no existe"
                    ),
                }

            if attempt.status == "completed":
                return {
                    "ok": False,
                    "error": (
                        "Este intento ya fue corregido"
                    ),
                    "attempt": attempt_to_dict(
                        attempt,
                        include_quiz=True,
                    ),
                }

            quiz_data = json.loads(
                attempt.questions_json
            )

            quiz_items = quiz_data["items"]

            if len(selected_answers) != len(
                quiz_items
            ):
                return {
                    "ok": False,
                    "error": (
                        "Debes enviar exactamente "
                        f"{len(quiz_items)} respuestas"
                    ),
                }

            invalid_answers = [
                answer
                for answer in selected_answers
                if answer not in {
                    0,
                    1,
                    2,
                    3,
                }
            ]

            if invalid_answers:
                return {
                    "ok": False,
                    "error": (
                        "Todas las respuestas deben ser "
                        "0, 1, 2 o 3"
                    ),
                }

            correct_count = 0
            result_items = []
            weak_topics = []

            for question_index, (
                item,
                selected_index,
            ) in enumerate(
                zip(
                    quiz_items,
                    selected_answers,
                )
            ):
                correct_index = item[
                    "correct_index"
                ]

                is_correct = (
                    selected_index
                    == correct_index
                )

                if is_correct:
                    correct_count += 1
                else:
                    weak_topics.append(
                        item["question"]
                    )

                answer_record = StudyAnswer(
                    attempt_id=attempt.id,
                    question_index=question_index,
                    question=item["question"],
                    selected_index=selected_index,
                    correct_index=correct_index,
                    is_correct=is_correct,
                    explanation=item.get(
                        "explanation"
                    ),
                    sources_json=json.dumps(
                        item.get(
                            "sources",
                            [],
                        ),
                        ensure_ascii=False,
                    ),
                )

                session.add(answer_record)

                result_items.append({
                    "question_index": (
                        question_index
                    ),
                    "question": item["question"],
                    "selected_index": (
                        selected_index
                    ),
                    "selected_answer": (
                        item["options"][
                            selected_index
                        ]
                    ),
                    "correct_index": (
                        correct_index
                    ),
                    "correct_answer": (
                        item["options"][
                            correct_index
                        ]
                    ),
                    "is_correct": is_correct,
                    "explanation": item.get(
                        "explanation"
                    ),
                    "sources": item.get(
                        "sources",
                        [],
                    ),
                })

            total_questions = len(
                quiz_items
            )

            score_percentage = round(
                correct_count
                / total_questions
                * 100,
                2,
            )

            results = {
                "correct_answers": correct_count,
                "incorrect_answers": (
                    total_questions
                    - correct_count
                ),
                "total_questions": (
                    total_questions
                ),
                "score_percentage": (
                    score_percentage
                ),
                "weak_topics": weak_topics,
                "items": result_items,
            }

            attempt.answers_json = json.dumps(
                selected_answers,
                ensure_ascii=False,
            )

            attempt.results_json = json.dumps(
                results,
                ensure_ascii=False,
            )

            attempt.correct_answers = (
                correct_count
            )

            attempt.score_percentage = (
                score_percentage
            )

            attempt.status = "completed"
            attempt.completed_at = (
                datetime.utcnow()
            )

            session.commit()
            session.refresh(attempt)

            return {
                "ok": True,
                "attempt": attempt_to_dict(
                    attempt
                ),
                "results": results,
            }

    @mcp.tool()
    def get_quiz_attempt(
        attempt_id: int,
    ) -> dict:
        """Obtiene un intento y su resultado completo."""

        with SessionLocal() as session:
            attempt = session.get(
                StudyAttempt,
                attempt_id,
            )

            if attempt is None:
                return {
                    "ok": False,
                    "error": (
                        "El intento no existe"
                    ),
                }

            return {
                "ok": True,
                "attempt": attempt_to_dict(
                    attempt,
                    include_quiz=True,
                ),
            }

    @mcp.tool()
    def list_quiz_attempts(
        subject_id: int | None = None,
        status: str | None = None,
        maximum_results: int = 50,
    ) -> dict:
        """Lista el historial de intentos."""

        if (
            maximum_results < 1
            or maximum_results > 200
        ):
            return {
                "ok": False,
                "error": (
                    "maximum_results debe estar "
                    "entre 1 y 200"
                ),
            }

        if status is not None:
            clean_status = (
                status.strip().casefold()
            )

            if clean_status not in {
                "pending",
                "completed",
            }:
                return {
                    "ok": False,
                    "error": (
                        "status debe ser pending "
                        "o completed"
                    ),
                }
        else:
            clean_status = None

        with SessionLocal() as session:
            statement = select(
                StudyAttempt
            )

            if subject_id is not None:
                statement = statement.where(
                    StudyAttempt.subject_id
                    == subject_id
                )

            if clean_status is not None:
                statement = statement.where(
                    StudyAttempt.status
                    == clean_status
                )

            statement = statement.order_by(
                StudyAttempt.started_at.desc(),
                StudyAttempt.id.desc(),
            ).limit(maximum_results)

            attempts = session.scalars(
                statement
            ).all()

            return {
                "ok": True,
                "result_count": len(
                    attempts
                ),
                "attempts": [
                    attempt_to_dict(
                        attempt
                    )
                    for attempt in attempts
                ],
            }

    @mcp.tool()
    def get_subject_study_progress(
        subject_id: int,
    ) -> dict:
        """
        Resume el progreso acumulado de una asignatura.
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

            attempts = session.scalars(
                select(StudyAttempt)
                .where(
                    StudyAttempt.subject_id
                    == subject_id,
                    StudyAttempt.status
                    == "completed",
                )
                .order_by(
                    StudyAttempt.completed_at.desc()
                )
            ).all()

            if not attempts:
                return {
                    "ok": True,
                    "subject": {
                        "id": subject.id,
                        "name": subject.name,
                    },
                    "completed_attempts": 0,
                    "message": (
                        "Todavía no hay intentos "
                        "completados"
                    ),
                }

            total_questions = sum(
                attempt.total_questions
                for attempt in attempts
            )

            total_correct = sum(
                attempt.correct_answers or 0
                for attempt in attempts
            )

            overall_score = round(
                total_correct
                / total_questions
                * 100,
                2,
            )

            weak_topics = []

            for attempt in attempts:
                if not attempt.results_json:
                    continue

                results = json.loads(
                    attempt.results_json
                )

                for weak_topic in results.get(
                    "weak_topics",
                    [],
                ):
                    weak_topics.append({
                        "attempt_id": attempt.id,
                        "topic": attempt.topic,
                        "question": weak_topic,
                    })

            return {
                "ok": True,
                "subject": {
                    "id": subject.id,
                    "name": subject.name,
                },
                "completed_attempts": len(
                    attempts
                ),
                "total_questions": (
                    total_questions
                ),
                "total_correct": total_correct,
                "overall_score_percentage": (
                    overall_score
                ),
                "weak_topic_count": len(
                    weak_topics
                ),
                "weak_topics": weak_topics[
                    :20
                ],
                "recent_attempts": [
                    attempt_to_dict(
                        attempt
                    )
                    for attempt in attempts[:10]
                ],
            }