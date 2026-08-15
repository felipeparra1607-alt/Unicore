import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.curriculum_engine import (
    build_curriculum_for_document,
    curriculum_for_subject,
    curriculum_scope,
    normalize_curriculum_name,
)
from src.database.models import (
    Base,
    CurriculumDocumentReference,
    CurriculumItem,
    Document,
    DocumentChunk,
    KnowledgeConcept,
    KnowledgeConnection,
    Subject,
)
from src.study_tools import study_mode_instructions
from src.v11_services import study_generation_context


class CurriculumEngineIsolatedTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "curriculum.sqlite3"
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as session:
            strategy = Subject(name="Strategic Management", academic_language="English")
            marketing = Subject(name="Marketing", academic_language="English")
            spanish = Subject(name="Historia", academic_language="Spanish")
            session.add_all([strategy, marketing, spanish])
            session.commit()
            self.strategy_id, self.marketing_id, self.spanish_id = strategy.id, marketing.id, spanish.id

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def _document(self, subject_id: int, title: str, text: str) -> int:
        with self.Session() as session:
            document = Document(
                title=title,
                file_path=f"{title}-{subject_id}.md",
                file_type="md",
                document_type="course_material",
                material_type="official_unit",
                subject_id=subject_id,
                extracted_text=text,
            )
            session.add(document)
            session.flush()
            session.add(DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                content=text,
                char_start=0,
                char_end=len(text),
                embedding_json="[1,0]",
            ))
            session.commit()
            return document.id

    def test_multi_document_merges_topics_preserves_sources_and_hierarchy(self):
        first_text = """# Mission, Vision and Values
Mission defines purpose, vision defines direction and values guide behaviour.

# Five Forces
The framework analyses industry structure.

## Supplier Power
Supplier concentration can increase bargaining power.
"""
        second_text = """# Mission and Vision
Mission and vision align strategic intent.

# Strategic Decision Making
Decisions connect diagnosis, policy and action.
"""
        first_id = self._document(self.strategy_id, "Lecture 1", first_text)
        second_id = self._document(self.strategy_id, "Lecture 1 Notes", second_text)
        self.assertTrue(build_curriculum_for_document(first_id, session_factory=self.Session)["ok"])
        self.assertTrue(build_curriculum_for_document(second_id, session_factory=self.Session)["ok"])

        with self.Session() as session:
            mission_topics = list(session.scalars(select(CurriculumItem).where(
                CurriculumItem.subject_id == self.strategy_id,
                CurriculumItem.item_type == "topic",
            )))
            mission_topics = [item for item in mission_topics if "mission" in item.normalized_name]
            self.assertEqual(len(mission_topics), 1)
            source_count = len(list(session.scalars(select(CurriculumDocumentReference).where(
                CurriculumDocumentReference.curriculum_item_id == mission_topics[0].id,
            ))))
            self.assertEqual(source_count, 2)
            five_forces = session.scalar(select(CurriculumItem).where(
                CurriculumItem.subject_id == self.strategy_id,
                CurriculumItem.normalized_name == normalize_curriculum_name("Five Forces"),
            ))
            supplier_power = session.scalar(select(CurriculumItem).where(
                CurriculumItem.subject_id == self.strategy_id,
                CurriculumItem.normalized_name == normalize_curriculum_name("Supplier Power"),
            ))
            self.assertIsNotNone(five_forces)
            self.assertEqual(supplier_power.parent_id, five_forces.id)

        curriculum = curriculum_for_subject(self.strategy_id, session_factory=self.Session)
        self.assertTrue(curriculum["units"])
        self.assertTrue(any(topic["name"] == "Five Forces" for unit in curriculum["units"] for topic in unit["topics"]))

    def test_numbered_lists_inside_explicit_unit_remain_topics(self):
        text = """Unit 1 — Foundations
1. Leaders are customer-obsessed
Customer focus shapes strategic priorities.
2. Leaders take ownership
Ownership supports long-term decisions.
Unit 1.1 — Strategic intent
Mission and vision establish direction.
"""
        document_id = self._document(self.strategy_id, "Leadership notes", text)
        self.assertTrue(build_curriculum_for_document(document_id, session_factory=self.Session)["ok"])

        with self.Session() as session:
            units = list(session.scalars(select(CurriculumItem).where(
                CurriculumItem.subject_id == self.strategy_id,
                CurriculumItem.item_type == "unit",
            )))
            topics = list(session.scalars(select(CurriculumItem).where(
                CurriculumItem.subject_id == self.strategy_id,
                CurriculumItem.item_type == "topic",
            )))
            self.assertEqual([item.name for item in units], ["Unit 1 — Foundations"])
            self.assertEqual(
                {item.name for item in topics},
                {"Leaders are customer-obsessed", "Leaders take ownership", "Unit 1.1 — Strategic intent"},
            )
            self.assertTrue(all(item.parent_id == units[0].id for item in topics))

    def test_cross_subject_shares_global_concept_without_mixing_curricula(self):
        strategy_document = self._document(self.strategy_id, "Strategy", "# Five Forces\nIndustry analysis.")
        marketing_document = self._document(self.marketing_id, "Marketing", "# Five Forces\nMarket structure context.")
        build_curriculum_for_document(strategy_document, session_factory=self.Session)
        build_curriculum_for_document(marketing_document, session_factory=self.Session)

        with self.Session() as session:
            concepts = list(session.scalars(select(KnowledgeConcept).where(
                KnowledgeConcept.normalized_name == normalize_curriculum_name("Five Forces")
            )))
            self.assertEqual({item.subject_id for item in concepts}, {self.strategy_id, self.marketing_id})
            self.assertEqual(len({item.global_concept_id for item in concepts}), 1)
            connection = session.scalar(select(KnowledgeConnection))
            self.assertEqual(connection.relationship, "equivalent")
            strategy_topic = session.scalar(select(CurriculumItem).where(
                CurriculumItem.subject_id == self.strategy_id,
                CurriculumItem.item_type == "topic",
            ))
            marketing_topic = session.scalar(select(CurriculumItem).where(
                CurriculumItem.subject_id == self.marketing_id,
                CurriculumItem.item_type == "topic",
            ))
            self.assertNotEqual(strategy_topic.id, marketing_topic.id)
            strategy_sources = list(session.scalars(select(CurriculumDocumentReference).where(
                CurriculumDocumentReference.curriculum_item_id == strategy_topic.id
            )))
            self.assertEqual({item.document_id for item in strategy_sources}, {strategy_document})

        scope = curriculum_scope(self.strategy_id, strategy_topic.id, session_factory=self.Session)
        self.assertEqual(scope["document_ids"], [strategy_document])
        self.assertTrue(scope["chunk_ids"])

    def test_academic_language_reaches_generation_context_and_prompts(self):
        english = study_generation_context(subject_id=self.strategy_id, session_factory=self.Session)
        spanish = study_generation_context(subject_id=self.spanish_id, session_factory=self.Session)
        self.assertEqual(english["academic_language"], "English")
        self.assertEqual(spanish["academic_language"], "Spanish")
        self.assertIn("English", study_mode_instructions("flashcards", 8, "advanced", academic_language=english["academic_language"]))
        self.assertIn("Spanish", study_mode_instructions("flashcards", 8, "advanced", academic_language=spanish["academic_language"]))


if __name__ == "__main__":
    unittest.main()
