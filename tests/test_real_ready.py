import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.conversation_memory import append_message, build_memory_context, create_conversation
from src.database.connection import Base
from src.database.models import (
    AcademicTask,
    Document,
    DocumentChunk,
    Professor,
    ProfessorPreference,
    ReviewItem,
    RubricCriterion,
    Subject,
)
from src.prompt_builder import build_academic_prompt
from src.providers.base import GenerationResult
from src.rag_tools import RankedChunk
from src.study_flows import persist_flashcards, reusable_flashcards
from src.frontend_api import UniCoreFrontendAPIHandler
from src.unicore_client import UniCoreMCPClient


class CountingProvider:
    calls = 0

    def generate(self, request):
        type(self).calls += 1
        if "flashcards" in request.system_message:
            text = json.dumps({
                "items": [
                    {"front": f"Pregunta {index}", "back": f"Respuesta {index}", "sources": ["FUENTE 1"]}
                    for index in range(1, 6)
                ]
            }, ensure_ascii=False)
        else:
            text = "Idea principal, explicación breve y ejemplo guiado. [FUENTE 1]"
        return GenerationResult(
            ok=True,
            provider="isolated-test",
            model="fixture",
            text=text,
            metadata={"api_called": True},
        )


class RealReadyIsolatedTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="unicore-real-ready-")
        database_path = Path(self.temporary_directory.name) / "fixture.db"
        self.engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        with self.Session() as session:
            subject = Subject(name="Historia real")
            other_subject = Subject(name="Biología ajena")
            empty_subject = Subject(name="Asignatura sin materiales")
            session.add_all([subject, other_subject, empty_subject]); session.flush()
            task = AcademicTask(
                subject_id=subject.id,
                title="Ensayo final",
                task_type="assignment",
                description="Comparar dos corrientes y justificar la tesis con evidencias.",
                notes="Extensión máxima: 1500 palabras.",
                priority=4,
            )
            professor = Professor(name="Profesora Ada", subject_id=subject.id)
            session.add_all([task, professor]); session.flush()
            session.add(ProfessorPreference(
                professor_id=professor.id, subject_id=subject.id, category="style",
                preference="Valora una tesis explícita y fuentes bien conectadas.", importance=5, confidence=5,
            ))
            session.add(RubricCriterion(
                subject_id=subject.id, professor_id=professor.id, title="Argumentación",
                description="Relaciona cada afirmación con una evidencia.", weight_percentage=40,
            ))
            document = Document(
                title="Guía de la asignatura", file_path=str(Path(self.temporary_directory.name) / "guide.txt"),
                file_type="txt", subject_id=subject.id,
                extracted_text="TEXTO_COMPLETO_QUE_NO_DEBE_ENTRAR " + "contenido " * 300,
            )
            other_document = Document(
                title="Documento de otra asignatura", file_path=str(Path(self.temporary_directory.name) / "other.txt"),
                file_type="txt", subject_id=other_subject.id, extracted_text="CONTEXTO_AJENO",
            )
            session.add_all([document, other_document]); session.flush()
            chunk = DocumentChunk(
                document_id=document.id, chunk_index=0,
                content="La evidencia relevante exige comparar causas y consecuencias.",
                char_start=0, char_end=65, source_label="p. 2", embedding_json="[1.0, 0.0]",
            )
            other_chunk = DocumentChunk(
                document_id=other_document.id, chunk_index=0, content="CONTEXTO_AJENO",
                char_start=0, char_end=14, source_label="p. 1", embedding_json="[1.0, 0.0]",
            )
            session.add_all([chunk, other_chunk]); session.commit()
            self.subject_id = subject.id
            self.other_subject_id = other_subject.id
            self.empty_subject_id = empty_subject.id
            self.task_id = task.id
            self.document_id = document.id
            self.chunk_id = chunk.id

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def _ranked_fixture(self, **kwargs):
        self.assertEqual(kwargs["subject_id"], self.subject_id)
        self.assertEqual(kwargs["document_id"], self.document_id)
        with self.Session() as session:
            chunk = session.get(DocumentChunk, self.chunk_id)
            document = session.get(Document, self.document_id)
            session.expunge(chunk); session.expunge(document)
        return [RankedChunk(chunk, document, 0.95, 0.8, 0.91)]

    def test_prompt_builder_selects_only_relevant_bounded_context(self):
        result = build_academic_prompt(
            objective="Revisar la introducción del ensayo",
            subject_id=self.subject_id,
            task_id=self.task_id,
            document_id=self.document_id,
            session_factory=self.Session,
            retriever=self._ranked_fixture,
        )
        self.assertTrue(result["ok"])
        self.assertIn("Ensayo final", result["prompt"])
        self.assertIn("tesis explícita", result["prompt"])
        self.assertIn("Argumentación", result["prompt"])
        self.assertIn("causas y consecuencias", result["prompt"])
        self.assertNotIn("CONTEXTO_AJENO", result["prompt"])
        self.assertNotIn("TEXTO_COMPLETO_QUE_NO_DEBE_ENTRAR", result["prompt"])
        self.assertLessEqual(result["retrieval"]["top_k"], 4)
        self.assertLessEqual(result["retrieval"]["context_characters"], 4200)
        self.assertFalse(result["retrieval"]["provider_called"])

    def test_explanation_uses_filtered_source_and_conversation_memory(self):
        CountingProvider.calls = 0
        with patch("src.rag_tools.SessionLocal", self.Session), patch(
            "src.rag_tools.create_embedding", lambda _value: [1.0, 0.0]
        ), patch("src.study_tools.create_provider", lambda **_kwargs: CountingProvider()), patch(
            "src.conversation_memory.SessionLocal", self.Session
        ):
            result = asyncio.run(self._call_tool("generate_study_material", {
                "topic": "causas y consecuencias", "subject_id": self.subject_id,
                "document_id": None, "mode": "explanation",
                "maximum_sources": 4, "maximum_context_characters": 4500,
            }))
            self.assertTrue(result["ok"])
            self.assertTrue(result["generated"])
            self.assertEqual(result["sources"][0]["document_id"], self.document_id)
            conversation = create_conversation(title="Tutoría", subject_id=self.subject_id, document_id=self.document_id)
            append_message(conversation["id"], "user", "Explícame las causas")
            append_message(conversation["id"], "assistant", result["content"], sources=result["sources"])
            memory = build_memory_context(conversation["id"])
            self.assertIn("Idea principal", memory["recent_messages"][-1]["content"])
            self.assertEqual(CountingProvider.calls, 1)

    def test_general_subject_scope_normalizes_topic_and_handles_no_material_humanely(self):
        handler = object.__new__(UniCoreFrontendAPIHandler)
        with patch("src.frontend_api.SessionLocal", self.Session):
            normalized = handler._study_topic({"topic": "toda la asignatura"}, self.subject_id, "explanation")
            self.assertEqual(normalized, "Explicación general de Historia real")
            normalized_blank = handler._study_topic({"topic": ""}, self.subject_id, "flashcards")
            self.assertEqual(normalized_blank, "Repaso general de Historia real")

        CountingProvider.calls = 0
        with patch("src.rag_tools.SessionLocal", self.Session), patch(
            "src.rag_tools.create_embedding", lambda _value: [1.0, 0.0]
        ), patch("src.study_tools.create_provider", lambda **_kwargs: CountingProvider()):
            flashcards = asyncio.run(self._call_tool("generate_study_material", {
                "topic": "Repaso general de Historia real",
                "subject_id": self.subject_id,
                "document_id": None,
                "mode": "flashcards",
                "item_count": 5,
                "maximum_sources": 4,
            }))
            no_material = asyncio.run(self._call_tool("generate_study_material", {
                "topic": "Explicación general de Asignatura sin materiales",
                "subject_id": self.empty_subject_id,
                "document_id": None,
                "mode": "explanation",
                "maximum_sources": 4,
            }))

        self.assertTrue(flashcards["generated"])
        self.assertEqual(len(flashcards["content"]["items"]), 5)
        self.assertTrue(no_material["ok"])
        self.assertFalse(no_material["generated"])
        self.assertEqual(no_material["source_count"], 0)
        self.assertEqual(CountingProvider.calls, 1)
        human_error = handler._study_material_unavailable(no_material, "explanation")
        self.assertEqual(human_error["code"], "study_material_missing")
        self.assertIn("Aún no hay material suficiente", human_error["error"])
        flashcard_error = handler._study_material_unavailable(no_material, "flashcards")
        self.assertIn("flashcards", flashcard_error["error"])

    def test_flashcards_are_batched_persisted_reused_and_rated(self):
        CountingProvider.calls = 0
        with patch("src.rag_tools.SessionLocal", self.Session), patch(
            "src.rag_tools.create_embedding", lambda _value: [1.0, 0.0]
        ), patch("src.study_tools.create_provider", lambda **_kwargs: CountingProvider()), patch(
            "src.review_tools.SessionLocal", self.Session
        ):
            generated = asyncio.run(self._call_tool("generate_study_material", {
                "topic": "causas", "subject_id": self.subject_id, "document_id": self.document_id,
                "mode": "flashcards", "item_count": 5, "maximum_sources": 4,
            }))
            self.assertTrue(generated["structured_output_validation"]["valid"])
            saved = persist_flashcards(
                subject_id=self.subject_id, topic="causas", cards=generated["content"]["items"],
                sources=generated["sources"], document_id=self.document_id, session_factory=self.Session,
            )
            self.assertEqual(len(saved["cards"]), 5)
            reused = reusable_flashcards(
                subject_id=self.subject_id, topic="causas", document_id=self.document_id,
                session_factory=self.Session,
            )
            self.assertEqual(len(reused), 5)
            self.assertEqual(CountingProvider.calls, 1)
            rated = asyncio.run(self._call_tool("submit_review_result", {
                "review_item_id": reused[0]["id"], "correct": True, "confidence": 5,
            }))
            self.assertTrue(rated["ok"])
            with self.Session() as session:
                item = session.get(ReviewItem, reused[0]["id"])
                self.assertEqual(item.repetition_count, 1)
                self.assertEqual(item.status, "reviewing")

    async def _call_tool(self, name, arguments):
        async with UniCoreMCPClient(transport="inprocess") as client:
            response = await client.call_tool(name, arguments)
        data = response["data"]
        return data["result"] if isinstance(data, dict) and set(data) == {"result"} else data


if __name__ == "__main__":
    unittest.main()
