import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

import src.curriculum_engine as curriculum_engine
import src.document_library as document_library
import src.rag_tools as rag_tools
from src.database.connection import Base
from src.database.migrate_material_classification import migrate_material_classification
from src.database.models import (
    CurriculumDocumentReference,
    CurriculumItem,
    Document,
    DocumentChunk,
    ExplanationCache,
    Subject,
)


class MaterialClassificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="unicore-material-types-")
        self.root = Path(self.temporary_directory.name)
        self.engine = create_engine(
            f"sqlite:///{(self.root / 'fixture.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as session:
            subject = Subject(name="Strategy")
            session.add(subject)
            session.commit()
            self.subject_id = subject.id
        self.patches = [
            patch.object(document_library, "SessionLocal", self.Session),
            patch.object(document_library, "MANAGED_DOCUMENTS_DIR", self.root / "materials"),
            patch.object(curriculum_engine, "SessionLocal", self.Session),
            patch.object(rag_tools, "SessionLocal", self.Session),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def _document(self, title, text_value, material_type, file_name):
        path = self.root / "materials" / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text_value, encoding="utf-8")
        with self.Session() as session:
            document = Document(
                title=title,
                file_path=str(path),
                file_type="txt",
                document_type="course_material",
                material_type=material_type,
                subject_id=self.subject_id,
                content_hash=f"hash-{file_name}",
                extracted_text=text_value,
                processing_status="ready",
            )
            session.add(document)
            session.commit()
            session.add(DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                content=text_value,
                char_start=0,
                char_end=len(text_value),
                chunking_strategy="hybrid_semantic",
                embedding_model="fixture",
                embedding_json="[1.0, 0.0]",
            ))
            session.commit()
            return document.id, path

    def test_additive_migration_defaults_existing_documents_to_other(self):
        legacy = create_engine(f"sqlite:///{(self.root / 'legacy.db').as_posix()}")
        with legacy.begin() as connection:
            connection.execute(text(
                "CREATE TABLE documents (id INTEGER PRIMARY KEY, title VARCHAR(250))"
            ))
            connection.execute(text("INSERT INTO documents (title) VALUES ('Legacy')"))
        migrate_material_classification(legacy)
        columns = {item["name"] for item in inspect(legacy).get_columns("documents")}
        self.assertIn("material_type", columns)
        self.assertIn("curriculum_unit_id", columns)
        with legacy.connect() as connection:
            self.assertEqual(
                connection.execute(text("SELECT material_type FROM documents")).scalar_one(),
                "other",
            )
        legacy.dispose()

    def test_reclassification_persists_unit_without_reembedding(self):
        with self.Session() as session:
            unit = CurriculumItem(
                subject_id=self.subject_id,
                item_type="unit",
                name="Unit 1 — Strategy",
                normalized_name="unit 1 strategy",
                position=1,
            )
            session.add(unit)
            session.commit()
            unit_id = unit.id
        document_id, _ = self._document(
            "Notes", "UNIT 1\nCorporate Values\nA sufficiently long explanation about values and strategy.",
            "other", "notes.txt",
        )
        with self.Session() as session:
            before = session.scalar(select(DocumentChunk.embedding_json).where(
                DocumentChunk.document_id == document_id
            ))
        result = document_library.update_document_classification(
            document_id,
            material_type="class_notes",
            curriculum_unit_id=unit_id,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["embeddings_reused"])
        with self.Session() as session:
            document = session.get(Document, document_id)
            after = session.scalar(select(DocumentChunk.embedding_json).where(
                DocumentChunk.document_id == document_id
            ))
            self.assertEqual(document.material_type, "class_notes")
            self.assertEqual(document.curriculum_unit_id, unit_id)
            self.assertEqual(before, after)

    def test_official_sources_share_one_unit_and_enrichment_does_not_create_units(self):
        official_text = "UNIT 1 — Strategy Overview\nCorporate Values\nA sufficiently long paragraph about corporate values and strategic direction."
        revised_text = "UNIT 1 revised\nCorporate Values\nA sufficiently long updated paragraph about corporate values and strategic direction."
        first_id, _ = self._document("UNIT 1", official_text, "official_unit", "unit-1.txt")
        second_id, _ = self._document("UNIT 1 revised", revised_text, "official_unit", "unit-1-revised.txt")
        notes_id, _ = self._document("Notes Unit 1", revised_text, "class_notes", "notes-unit-1.txt")
        assignment_id, _ = self._document(
            "Assignment", "Assignment brief\nWrite a report with evidence and recommendations.",
            "assignment", "assignment.txt",
        )
        for document_id in (first_id, second_id, notes_id, assignment_id):
            result = curriculum_engine.build_curriculum_for_document(
                document_id, session_factory=self.Session
            )
            self.assertTrue(result["ok"])
        curriculum = curriculum_engine.curriculum_for_subject(
            self.subject_id, session_factory=self.Session
        )
        self.assertEqual(len(curriculum["units"]), 1)
        unit = curriculum["units"][0]
        self.assertGreaterEqual(len(unit["sources"]), 3)
        corporate = [topic for topic in unit["topics"] if "Corporate Values" in topic["name"]]
        self.assertEqual(len(corporate), 1)
        self.assertGreaterEqual(len(corporate[0]["sources"]), 3)

    def test_ambiguous_unit_number_is_not_merged(self):
        with self.Session() as session:
            session.add_all([
                CurriculumItem(subject_id=self.subject_id, item_type="unit", name="Unit 1 Strategy", normalized_name="unit 1 strategy", position=1),
                CurriculumItem(subject_id=self.subject_id, item_type="unit", name="Unit 1 Accounting", normalized_name="unit 1 accounting", position=2),
            ])
            session.commit()
            match, reason = curriculum_engine.find_canonical_unit(
                session, subject_id=self.subject_id, name="Unit 1 Finance"
            )
            self.assertIsNone(match)
            self.assertEqual(reason, "ambiguous")

    def test_delete_cleans_document_relations_but_keeps_shared_curriculum(self):
        first_id, first_path = self._document("Official", "Unit material", "official_unit", "official.txt")
        second_id, _ = self._document("Second source", "More unit material", "official_unit", "second.txt")
        with self.Session() as session:
            unit = CurriculumItem(
                subject_id=self.subject_id, item_type="unit", name="Unit 1",
                normalized_name="unit 1", position=1,
            )
            session.add(unit)
            session.flush()
            session.add_all([
                CurriculumDocumentReference(curriculum_item_id=unit.id, document_id=first_id),
                CurriculumDocumentReference(curriculum_item_id=unit.id, document_id=second_id),
                ExplanationCache(
                    subject_id=self.subject_id, document_id=first_id,
                    curriculum_item_id=unit.id, topic_key="unit 1", difficulty="intermedio",
                    material_fingerprint="fixture", content="Cached", sources_json="[]",
                ),
            ])
            session.commit()
            unit_id = unit.id
        self.assertTrue(document_library.delete_managed_document(first_id))
        self.assertFalse(first_path.exists())
        with self.Session() as session:
            self.assertIsNone(session.get(Document, first_id))
            self.assertEqual(session.scalar(select(DocumentChunk).where(DocumentChunk.document_id == first_id)), None)
            self.assertIsNotNone(session.get(CurriculumItem, unit_id))
            remaining = list(session.scalars(select(CurriculumDocumentReference).where(
                CurriculumDocumentReference.curriculum_item_id == unit_id
            )))
            self.assertEqual([item.document_id for item in remaining], [second_id])
            self.assertIsNone(session.scalar(select(ExplanationCache).where(
                ExplanationCache.document_id == first_id
            )))

    def test_rag_context_changes_material_priority_without_excluding_sources(self):
        official_id, _ = self._document("Official", "same evidence", "official_unit", "rag-official.txt")
        assignment_id, _ = self._document("Assignment", "same evidence", "assignment", "rag-assignment.txt")
        with patch.object(rag_tools, "create_embedding", return_value=[1.0, 0.0]), patch.object(
            rag_tools, "embedding_from_json", return_value=[1.0, 0.0]
        ), patch.object(rag_tools, "cosine_similarity", return_value=0.5):
            study = rag_tools.retrieve_ranked_chunks(
                "same evidence", self.subject_id, 0.75, ranking_context="study"
            )
            task = rag_tools.retrieve_ranked_chunks(
                "same evidence", self.subject_id, 0.75, ranking_context="task"
            )
        self.assertEqual(study[0].document.id, official_id)
        self.assertEqual(task[0].document.id, assignment_id)
        self.assertEqual({item.document.id for item in study}, {official_id, assignment_id})


if __name__ == "__main__":
    unittest.main()
