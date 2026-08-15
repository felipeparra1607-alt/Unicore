import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.chunk_tools as chunk_tools
import src.curriculum_engine as curriculum_engine
import src.document_library as document_library
import src.frontend_api as frontend_api
import src.mcp_resources as mcp_resources
import src.server as server_module
from src.database.connection import Base
from src.database.models import Document, ReviewItem, Subject
from src.decision_engine import ensure_academic_task_candidate
from src.v11_services import cached_explanation, leitner_overview, rate_leitner_card, reject_flashcard, store_explanation_cache


class ClosureCorrectionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="unicore-closure-")
        root = Path(self.temporary_directory.name)
        self.engine = create_engine(f"sqlite:///{(root / 'fixture.db').as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as session:
            subject = Subject(name="Strategic Management", academic_language="English", academic_language_configured=True)
            session.add(subject); session.commit(); self.subject_id = subject.id
        self.patches = [
            patch.object(document_library, "SessionLocal", self.Session),
            patch.object(document_library, "MANAGED_DOCUMENTS_DIR", root / "materials"),
            patch.object(server_module, "SessionLocal", self.Session),
            patch.object(chunk_tools, "SessionLocal", self.Session),
            patch.object(curriculum_engine, "SessionLocal", self.Session),
            patch.object(mcp_resources, "SessionLocal", self.Session),
            patch.object(frontend_api, "SessionLocal", self.Session),
            patch.object(document_library, "build_curriculum_for_document", lambda document_id: curriculum_engine.build_curriculum_for_document(document_id, session_factory=self.Session)),
        ]
        for active_patch in self.patches: active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches): active_patch.stop()
        self.engine.dispose(); self.temporary_directory.cleanup()

    def test_upload_size_contract(self):
        for size in (10 * 1024 * 1024, 25 * 1024 * 1024, document_library.MAXIMUM_DOCUMENT_BYTES):
            self.assertEqual(document_library._validate_upload("notes.pdf", size)[1], ".pdf")
        with self.assertRaisesRegex(ValueError, "50 MB"):
            document_library._validate_upload("notes.pdf", document_library.MAXIMUM_DOCUMENT_BYTES + 1)

    def test_planner_reserves_real_task_without_persisting_session_edits(self):
        reviews = [{"type": "review", "source_id": 2, "score": 90, "suggested_minutes": 30, "allocated_minutes": 30}]
        task = {"type": "task", "source_id": 7, "score": 45, "suggested_minutes": 30}
        first = ensure_academic_task_candidate(reviews, [*reviews, task], 60, 3)
        self.assertTrue(any(item["type"] == "task" for item in first))
        local = [item for item in first if item["source_id"] != 7]
        self.assertFalse(any(item["source_id"] == 7 for item in local))
        replanned = ensure_academic_task_candidate(reviews, [*reviews, task], 60, 3)
        self.assertTrue(any(item["source_id"] == 7 for item in replanned))

    def test_cache_ignores_unrelated_material_and_invalidates_relevant_scope(self):
        with self.Session() as session:
            relevant = Document(title="Values", file_path="values.pdf", file_type="pdf", subject_id=self.subject_id, content_hash="relevant-a", curriculum_processed_at=datetime.utcnow())
            session.add(relevant); session.commit(); relevant_id = relevant.id
        arguments = dict(subject_id=self.subject_id, document_id=None, curriculum_item_id=10, topic="Corporate Values", difficulty="intermedio", allowed_document_ids=[relevant_id], session_factory=self.Session)
        store_explanation_cache(**arguments, content="Saved", sources=[])
        self.assertIsNotNone(cached_explanation(**arguments))
        with self.Session() as session:
            unrelated = Document(title="Accounting", file_path="accounting.pdf", file_type="pdf", subject_id=self.subject_id, content_hash="unrelated", curriculum_processed_at=datetime.utcnow())
            session.add(unrelated); session.commit()
        self.assertIsNotNone(cached_explanation(**arguments))
        with self.Session() as session:
            new_relevant = Document(title="Values update", file_path="values-update.pdf", file_type="pdf", subject_id=self.subject_id, content_hash="relevant-b", curriculum_processed_at=datetime.utcnow())
            session.add(new_relevant); session.commit(); new_relevant_id = new_relevant.id
        self.assertIsNone(cached_explanation(**{**arguments, "allowed_document_ids": [relevant_id, new_relevant_id]}))

    def test_flashcard_easy_advances_two_boxes_and_reject_leaves_leitner(self):
        with self.Session() as session:
            card = ReviewItem(subject_id=self.subject_id, topic="Strategy", question="What is strategy?", correct_answer="A coherent set of choices.", status="learning", priority=3, repetition_count=0, correct_streak=0, incorrect_count=0, interval_days=1, ease_factor=2.5, leitner_box=1, cognitive_level="understanding", next_review_at=datetime.utcnow())
            session.add(card); session.commit(); card_id = card.id
        rated = rate_leitner_card(card_id, rating="easy", session_factory=self.Session)
        self.assertEqual(rated["card"]["leitner_box"], 3)
        self.assertTrue(reject_flashcard(card_id, session_factory=self.Session)["ok"])
        self.assertEqual(leitner_overview(subject_id=self.subject_id, session_factory=self.Session)["cards"], [])

    def test_real_binary_upload_returns_202_and_reaches_ready(self):
        fixture_value = os.getenv("UNICORE_UPLOAD_FIXTURE")
        if not fixture_value:
            self.skipTest("UNICORE_UPLOAD_FIXTURE no configurado")
        fixture = Path(fixture_value)
        self.assertGreater(fixture.stat().st_size, 8 * 1024 * 1024)
        self.assertLess(fixture.stat().st_size, document_library.MAXIMUM_DOCUMENT_BYTES)
        httpd = frontend_api.ThreadingHTTPServer(("127.0.0.1", 0), frontend_api.UniCoreFrontendAPIHandler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True); worker.start()
        try:
            port = httpd.server_address[1]
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            connection.request("OPTIONS", f"/api/subjects/{self.subject_id}/materials", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            preflight = connection.getresponse(); preflight.read(); self.assertEqual(preflight.status, 204)
            body = fixture.read_bytes()
            connection.request("POST", f"/api/subjects/{self.subject_id}/materials?file_name=UNIT%201%20%281%29.pdf", body=body, headers={"Origin": "http://127.0.0.1:5173", "Content-Type": "application/pdf"})
            response = connection.getresponse(); payload = json.loads(response.read()); self.assertEqual(response.status, 202); self.assertFalse(payload["duplicate"])
            status = "processing"
            deadline = time.time() + 180
            while status == "processing" and time.time() < deadline:
                time.sleep(0.5)
                connection.request("GET", f"/api/subjects/{self.subject_id}/documents", headers={"Origin": "http://127.0.0.1:5173"})
                poll = connection.getresponse(); poll_payload = json.loads(poll.read()); self.assertEqual(poll.status, 200)
                status = poll_payload["documents"][0]["processing_status"]
            self.assertEqual(status, "ready", poll_payload["documents"][0].get("processing_error"))
            self.assertGreater(poll_payload["documents"][0]["chunk_count"], 0)
            connection.request("POST", f"/api/subjects/{self.subject_id}/materials?file_name=UNIT%201%20%281%29.pdf", body=body, headers={"Origin": "http://127.0.0.1:5173", "Content-Type": "application/pdf"})
            duplicate = connection.getresponse(); duplicate_payload = json.loads(duplicate.read()); self.assertEqual(duplicate.status, 200); self.assertTrue(duplicate_payload["duplicate"])
        finally:
            httpd.shutdown(); httpd.server_close(); worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
