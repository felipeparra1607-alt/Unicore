import base64
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from uuid import uuid4

from src.agent_context import build_selective_agent_context, needs_document_retrieval
from src.conversation_memory import (
    append_message,
    build_memory_context,
    create_conversation,
    delete_conversation,
    get_conversation,
    refresh_summary_if_needed,
)
from src.database.migrate_conversations import migrate_conversations
from src.database.migrate_v11 import migrate_v11
from src.database.connection import SessionLocal
from src.database.models import Subject
from src.document_library import delete_managed_document, get_document_content, ingest_document_bytes
from src.frontend_api import UniCoreFrontendAPIHandler
from src.rag_tools import retrieve_ranked_chunks, select_context_chunks


class DemoV1PersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        migrate_conversations()
        migrate_v11()
        with SessionLocal() as session:
            subject = session.query(Subject).order_by(Subject.id).first()
            cls.created_subject = subject is None
            if subject is None:
                subject = Subject(name="Asignatura temporal Demo V1")
                session.add(subject)
                session.commit()
                session.refresh(subject)
            cls.subject_id = subject.id

    @classmethod
    def tearDownClass(cls):
        if cls.created_subject:
            with SessionLocal() as session:
                subject = session.get(Subject, cls.subject_id)
                if subject is not None:
                    session.delete(subject)
                    session.commit()

    def test_document_ingestion_duplicate_open_and_filtered_retrieval(self):
        marker = "CLAVE-BOREAL-" + uuid4().hex
        content = (
            f"La contraseña conceptual del seminario es {marker}. "
            "El protocolo exige tres revisiones antes de entregar."
        ).encode("utf-8")
        document_id = None
        try:
            created = ingest_document_bytes(
                file_name="demo-v1-test.txt",
                content=content,
                subject_id=self.subject_id,
            )
            self.assertTrue(created["ok"])
            self.assertFalse(created["duplicate"])
            document_id = created["document"]["id"]
            self.assertGreater(created["document"]["chunk_count"], 0)

            duplicate = ingest_document_bytes(
                file_name="demo-v1-duplicate.txt",
                content=content,
                subject_id=self.subject_id,
            )
            self.assertTrue(duplicate["duplicate"])
            self.assertEqual(duplicate["document"]["id"], document_id)

            opened = get_document_content(document_id)
            self.assertIsNotNone(opened)
            self.assertIn(marker, opened["content"])

            ranked = retrieve_ranked_chunks(
                query=marker,
                subject_id=self.subject_id,
                document_id=document_id,
                semantic_weight=0.75,
            )
            selected = select_context_chunks(
                ranked_chunks=ranked,
                minimum_score=0.20,
                maximum_sources=4,
                maximum_context_characters=4500,
                redundancy_threshold=0.80,
            )
            self.assertTrue(selected)
            self.assertTrue(all(item.document.id == document_id for item in selected))
            self.assertIn(marker, selected[0].chunk.content)
        finally:
            if document_id is not None:
                delete_managed_document(document_id)

    def test_persistent_memory_recent_window_and_summary(self):
        conversation = create_conversation(title="Conversación temporal Demo V1")
        conversation_id = conversation["id"]
        try:
            for index in range(7):
                append_message(conversation_id, "user", f"Pregunta {index} sobre X e Y")
                append_message(conversation_id, "assistant", f"Respuesta {index} compara X e Y")
            summary = refresh_summary_if_needed(conversation_id)
            memory = build_memory_context(conversation_id)
            persisted = get_conversation(conversation_id)

            self.assertIsNotNone(summary)
            self.assertLessEqual(len(memory["recent_messages"]), 8)
            self.assertIn("X e Y", memory["recent_messages"][-1]["content"])
            self.assertEqual(len(persisted["messages"]), 14)
            self.assertTrue(persisted["summary_available"])
        finally:
            delete_conversation(conversation_id)

    def test_retrieval_gate_uses_recent_memory_without_documents(self):
        self.assertFalse(needs_document_retrieval("hola", document_id=1))
        self.assertFalse(needs_document_retrieval("explícamelo más sencillo", document_id=1))
        self.assertTrue(needs_document_retrieval("¿Qué dice este material?", document_id=1))
        context = build_selective_agent_context(
            message="¿Y cuál de los dos usarías?",
            memory={
                "summary": None,
                "recent_messages": [
                    {"role": "user", "content": "¿Qué diferencia hay entre X e Y?"},
                    {"role": "assistant", "content": "X prioriza velocidad; Y precisión."},
                ],
            },
        )
        self.assertFalse(context["retrieval"]["used"])
        self.assertIn("X prioriza velocidad", context["context"])


class DemoV1EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        migrate_conversations()
        migrate_v11()
        with SessionLocal() as session:
            subject = session.query(Subject).order_by(Subject.id).first()
            cls.created_subject = subject is None
            if subject is None:
                subject = Subject(name="Asignatura temporal endpoints Demo V1")
                session.add(subject)
                session.commit()
                session.refresh(subject)
            cls.subject_id = subject.id
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), UniCoreFrontendAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        if cls.created_subject:
            with SessionLocal() as session:
                subject = session.get(Subject, cls.subject_id)
                if subject is not None:
                    session.delete(subject)
                    session.commit()

    def _json(self, path, method="GET", payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_conversation_create_list_open_delete_endpoints(self):
        status, created = self._json(
            "/api/conversations",
            method="POST",
            payload={"title": "Endpoint temporal Demo V1", "context_type": "general"},
        )
        self.assertEqual(status, 201)
        conversation_id = created["conversation"]["id"]
        try:
            _, listed = self._json("/api/conversations")
            self.assertTrue(any(item["id"] == conversation_id for item in listed["conversations"]))
            _, opened = self._json(f"/api/conversations/{conversation_id}")
            self.assertEqual(opened["conversation"]["title"], "Endpoint temporal Demo V1")
        finally:
            status, _ = self._json(f"/api/conversations/{conversation_id}", method="DELETE")
            self.assertEqual(status, 200)

    def test_material_upload_open_and_duplicate_endpoints(self):
        marker = "ENDPOINT-MATERIAL-" + uuid4().hex
        encoded = base64.b64encode(f"Contenido exclusivo {marker}.".encode()).decode()
        document_id = None
        try:
            status, uploaded = self._json(
                f"/api/subjects/{self.subject_id}/materials",
                method="POST",
                payload={"file_name": "endpoint-demo.txt", "content_base64": encoded},
            )
            self.assertEqual(status, 201)
            document_id = uploaded["document"]["id"]
            self.assertGreater(uploaded["document"]["chunk_count"], 0)

            _, opened = self._json(f"/api/documents/{document_id}")
            self.assertIn(marker, opened["content"])

            status, duplicate = self._json(
                f"/api/subjects/{self.subject_id}/materials",
                method="POST",
                payload={"file_name": "endpoint-duplicate.txt", "content_base64": encoded},
            )
            self.assertEqual(status, 200)
            self.assertTrue(duplicate["duplicate"])
        finally:
            if document_id is not None:
                delete_managed_document(document_id)


if __name__ == "__main__":
    unittest.main()
