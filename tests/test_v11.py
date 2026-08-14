import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from src.database.connection import Base
from src.database.models import (
    Document,
    DocumentChunk,
    FlashcardDraft,
    ProfessorPreference,
    ReviewItem,
    StudentModelEvidence,
    Subject,
    TokenUsage,
    WrittenEvaluation,
)
from src.providers.base import GenerationResult
from src.agent_context import requests_global_academic_memory
from src.rag_tools import RankedChunk
from src.v11_services import (
    _professor_context,
    academic_map,
    add_professor_criterion,
    assign_professor,
    create_flashcard_drafts,
    decide_flashcard_draft,
    evaluate_written_answer,
    hierarchical_retrieval,
    leitner_overview,
    move_flashcard,
    professors_overview,
    rate_leitner_card,
    record_token_usage,
    student_model,
    token_analytics,
)


class StrictEvaluationProvider:
    def generate(self, _request):
        return GenerationResult(
            ok=True,
            provider="isolated-test",
            model="fixture",
            text=json.dumps({
                "overall_score": 68,
                "dimensions": [
                    {"name": "content_accuracy", "score": 72, "feedback": "Correcto pero incompleto."},
                    {"name": "depth_of_analysis", "score": 55, "feedback": "Falta derivar la conclusión."},
                    {"name": "academic_english", "score": 78, "feedback": "Registro adecuado."},
                ],
                "errors": ["La conclusión no se justifica con evidencia."],
                "improvements": ["Conecta explícitamente evidencia y conclusión."],
                "example_improvement": "Therefore, the evidence supports the conclusion because…",
            }),
            input_tokens=240,
            output_tokens=110,
            total_tokens=350,
            metadata={"api_called": True},
        )


class V11IsolatedTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="unicore-v11-")
        path = Path(self.temporary_directory.name) / "fixture.db"
        self.engine = create_engine(f"sqlite:///{path.as_posix()}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        with self.Session() as session:
            current = Subject(name="Strategic Management", academic_language="English", academic_year="2026")
            historical = Subject(name="Marketing Foundations", academic_language="English", academic_year="2024")
            session.add_all([current, historical]); session.flush()
            current_doc = Document(title="Strategy notes", file_path="fixture-current.md", file_type="md", document_type="course_material", subject_id=current.id)
            historical_doc = Document(title="Brand equity notes", file_path="fixture-history.md", file_type="md", document_type="course_material", subject_id=historical.id)
            session.add_all([current_doc, historical_doc]); session.flush()
            current_chunk = DocumentChunk(document_id=current_doc.id, chunk_index=0, content="Competitive advantage depends on valuable resources.", char_start=0, char_end=52, embedding_json="[1,0]")
            historical_chunk = DocumentChunk(document_id=historical_doc.id, chunk_index=0, content="Brand equity can reinforce differentiation.", char_start=0, char_end=42, embedding_json="[1,0]")
            session.add_all([current_chunk, historical_chunk]); session.flush()
            review = ReviewItem(
                subject_id=current.id,
                topic="Competitive advantage",
                question="How does a valuable resource create advantage?",
                correct_answer="It creates value when competitors cannot easily imitate it.",
                status="reviewing",
                priority=3,
                repetition_count=1,
                correct_streak=1,
                incorrect_count=0,
                interval_days=3,
                ease_factor=2.5,
                leitner_box=2,
                cognitive_level="application",
                next_review_at=datetime.utcnow(),
            )
            session.add(review); session.commit()
            self.subject_id = current.id
            self.other_subject_id = historical.id
            self.review_id = review.id
            self.current_document_id = current_doc.id
            self.historical_document_id = historical_doc.id
            self.current_chunk_id = current_chunk.id
            self.historical_chunk_id = historical_chunk.id

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_leitner_transitions_and_manual_control(self):
        difficult = rate_leitner_card(self.review_id, rating="difficult", session_factory=self.Session)
        self.assertEqual(difficult["previous_box"], 2)
        self.assertEqual(difficult["card"]["leitner_box"], 1)
        good = rate_leitner_card(self.review_id, rating="good", session_factory=self.Session)
        self.assertEqual(good["card"]["leitner_box"], 2)
        moved = move_flashcard(self.review_id, target_box=5, session_factory=self.Session)
        self.assertEqual(moved["card"]["leitner_box"], 5)
        self.assertEqual(moved["card"]["interval_days"], 30)
        early = move_flashcard(self.review_id, review_earlier=True, session_factory=self.Session)
        self.assertLessEqual(datetime.fromisoformat(early["card"]["next_review_at"]), datetime.utcnow())
        overview = leitner_overview(subject_id=self.subject_id, session_factory=self.Session)
        self.assertEqual(overview["boxes"][4]["count"], 1)

    def test_draft_duplicate_rejection_and_acceptance(self):
        drafts = create_flashcard_drafts(
            subject_id=self.subject_id,
            topic="Competitive advantage",
            cards=[
                {"front": "How does a valuable resource create advantage?", "back": "Through value and inimitability."},
                {"front": "Apply VRIO to a scarce capability.", "back": "Test value, rarity, imitability and organization."},
            ],
            sources=[],
            cognitive_level="mixed",
            answer_mode="mental",
            session_factory=self.Session,
        )
        self.assertTrue(drafts[0]["probable_duplicate"])
        before = self._count(ReviewItem)
        rejected = decide_flashcard_draft(drafts[0]["id"], accept=False, rejection_reason="Repetida", session_factory=self.Session)
        self.assertFalse(rejected["accepted"])
        self.assertEqual(self._count(ReviewItem), before)
        accepted = decide_flashcard_draft(drafts[1]["id"], accept=True, session_factory=self.Session)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["card"]["leitner_box"], 1)
        self.assertEqual(self._count(ReviewItem), before + 1)
        with self.Session() as session:
            rejected_record = session.get(FlashcardDraft, drafts[0]["id"])
            self.assertEqual(rejected_record.rejection_reason, "Repetida")

    def test_written_evaluation_persists_and_updates_student_model(self):
        result = evaluate_written_answer(
            review_item_id=self.review_id,
            answer_text="A valuable resource creates advantage only when it is rare and difficult to imitate, so the conclusion must follow from the VRIO evidence.",
            session_factory=self.Session,
            provider_factory=lambda **_kwargs: StrictEvaluationProvider(),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["evaluation"]["overall_score"], 68)
        self.assertEqual(result["usage"]["total_tokens"], 350)
        self.assertEqual(self._count(WrittenEvaluation), 1)
        self.assertEqual(self._count(StudentModelEvidence), 3)
        self.assertEqual(self._count(TokenUsage), 1)
        model = student_model(subject_id=self.subject_id, session_factory=self.Session)
        dimensions = {item["dimension"] for item in model["dimensions"]}
        self.assertIn("depth_of_analysis", dimensions)
        with self.Session() as session:
            item = session.get(ReviewItem, self.review_id)
            self.assertEqual(item.leitner_box, 2)

    def test_student_model_uses_recency_and_removes_overcome_weakness(self):
        origin = datetime.utcnow() - timedelta(days=30)
        with self.Session() as session:
            for index in range(6):
                session.add(StudentModelEvidence(subject_id=self.subject_id, dimension="argument_quality", score=30, source_type="fixture", source_id=index + 1, observed_at=origin + timedelta(days=index)))
            for index in range(3):
                session.add(StudentModelEvidence(subject_id=self.subject_id, dimension="argument_quality", score=60, source_type="fixture", source_id=20 + index, observed_at=origin + timedelta(days=10 + index)))
            session.commit()
        improving = student_model(subject_id=self.subject_id, session_factory=self.Session)
        self.assertIn("argument_quality", {item["dimension"] for item in improving["areas_for_improvement"]})
        with self.Session() as session:
            for index in range(20):
                session.add(StudentModelEvidence(subject_id=self.subject_id, dimension="argument_quality", score=95, source_type="fixture", source_id=40 + index, observed_at=datetime.utcnow() + timedelta(seconds=index)))
            session.commit()
        recovered = student_model(subject_id=self.subject_id, session_factory=self.Session)
        self.assertNotIn("argument_quality", {item["dimension"] for item in recovered["areas_for_improvement"]})
        self.assertIn("argument_quality", {item["dimension"] for item in recovered["strengths"]})

    def test_professor_assignment_and_criteria_ranking(self):
        created = assign_professor(subject_id=self.subject_id, name="Professor Ada", session_factory=self.Session)
        professor_id = created["professor"]["id"]
        assigned = assign_professor(subject_id=self.other_subject_id, professor_id=professor_id, session_factory=self.Session)
        self.assertTrue(assigned["ok"])
        add_professor_criterion(professor_id=professor_id, subject_id=self.subject_id, text_value="Use concrete evidence.", importance=3, session_factory=self.Session)
        add_professor_criterion(professor_id=professor_id, subject_id=self.subject_id, text_value="Conclusions must derive from analysis.", importance=5, session_factory=self.Session)
        overview = professors_overview(session_factory=self.Session)
        professor = next(item for item in overview["professors"] if item["id"] == professor_id)
        self.assertEqual({item["id"] for item in professor["subjects"]}, {self.subject_id, self.other_subject_id})
        with self.Session() as session:
            context = _professor_context(session, self.subject_id)
        self.assertLess(context.index("Conclusions must derive"), context.index("Use concrete evidence"))

    def test_token_aggregation(self):
        record_token_usage(usage={"input_tokens": 100, "output_tokens": 40, "total_tokens": 140}, feature="agent", subject_id=self.subject_id, session_factory=self.Session)
        record_token_usage(usage={"input_tokens": 60, "output_tokens": 20, "total_tokens": 80}, feature="flashcards", subject_id=self.other_subject_id, session_factory=self.Session)
        result = token_analytics(days=7, session_factory=self.Session)
        self.assertEqual(result["today"], 220)
        self.assertEqual(result["this_week"], 220)
        by_subject = {item["subject_id"]: item["total_tokens"] for item in result["by_subject"]}
        self.assertEqual(by_subject[self.subject_id], 140)
        self.assertEqual(by_subject[self.other_subject_id], 80)

    def test_academic_memory_is_subject_first_and_global_only_when_requested(self):
        self.assertFalse(requests_global_academic_memory("Explica este concepto"))
        self.assertTrue(requests_global_academic_memory("Relaciona esto con otras asignaturas"))
        calls = []
        with self.Session() as session:
            current_document = session.get(Document, self.current_document_id)
            historical_document = session.get(Document, self.historical_document_id)
            current_chunk = session.get(DocumentChunk, self.current_chunk_id)
            historical_chunk = session.get(DocumentChunk, self.historical_chunk_id)
            for item in (current_document, historical_document, current_chunk, historical_chunk):
                session.expunge(item)
        current = RankedChunk(current_chunk, current_document, .9, .8, .88)
        historical = RankedChunk(historical_chunk, historical_document, .85, .7, .81)
        def retriever(**kwargs):
            calls.append(kwargs["subject_id"])
            return [current] if kwargs["subject_id"] == self.subject_id else [current, historical]
        local = hierarchical_retrieval(query="advantage", subject_id=self.subject_id, include_global=False, retriever=retriever)
        self.assertEqual(calls, [self.subject_id])
        self.assertEqual(local["source_count"], 1)
        calls.clear()
        global_result = hierarchical_retrieval(query="advantage", subject_id=self.subject_id, include_global=True, retriever=retriever)
        self.assertEqual(calls, [self.subject_id, None])
        self.assertEqual(len(global_result["current"]), 1)
        self.assertEqual(len(global_result["historical"]), 1)
        self.assertEqual(global_result["historical"][0].document.subject_id, self.other_subject_id)

    def test_academic_map_does_not_invent_connections(self):
        result = academic_map(session_factory=self.Session)
        self.assertEqual(result["connections"], [])

    def _count(self, model):
        with self.Session() as session:
            return session.scalar(select(func.count()).select_from(model))


if __name__ == "__main__":
    unittest.main()
