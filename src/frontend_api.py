import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.decision_engine import build_decision_plan
from src.knowledge_map import build_subject_knowledge_map
from src.mcp_resources import _build_subject_reviews, _build_subject_study, _build_tasks
from src.runtime_context import build_runtime_context
from src.unicore_dashboard import build_dashboard_data
from src.unicore_agent import UniCoreAgent

HOST = "127.0.0.1"
PORT = 8766


class UniCoreFrontendAPIHandler(BaseHTTPRequestHandler):
    def _allowed_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        if origin in {"http://127.0.0.1:5173", "http://localhost:5173"}:
            return origin
        return "http://127.0.0.1:5173"

    def _send_json(self, payload: dict, status_code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._allowed_origin())
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._allowed_origin())
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > 65536:
            raise ValueError("Cuerpo JSON vacío o demasiado grande")
        payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("El cuerpo debe ser un objeto JSON")
        return payload

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        try:
            if parsed.path == "/api/health":
                self._send_json({"ok": True, "service": "unicore-frontend-api"})
                return

            if parsed.path == "/api/dashboard":
                subject_value = query.get("subject_id", [None])[0]
                subject_id = int(subject_value) if subject_value not in (None, "") else None
                data = build_dashboard_data(subject_id=subject_id)
                self._send_json(data, 200 if data.get("ok") else 400)
                return

            if parsed.path == "/api/decision-plan":
                available_minutes = int(query.get("available_minutes", ["60"])[0])
                maximum_actions = int(query.get("maximum_actions", ["3"])[0])
                subject_value = query.get("subject_id", [None])[0]
                subject_id = int(subject_value) if subject_value not in (None, "") else None
                data = build_decision_plan(
                    available_minutes=available_minutes,
                    subject_id=subject_id,
                    maximum_actions=maximum_actions,
                )
                self._send_json(data, 200 if data.get("ok") else 400)
                return

            if parsed.path == "/api/tasks":
                subject_value = query.get("subject_id", [None])[0]
                subject_id = int(subject_value) if subject_value not in (None, "") else None
                data = _build_tasks(subject_id=subject_id)
                self._send_json(data, 200 if data.get("ok") else 400)
                return

            if parsed.path == "/api/study":
                subject_value = query.get("subject_id", [None])[0]
                if subject_value in (None, ""):
                    self._send_json({"ok": False, "error": "subject_id es obligatorio"}, 400)
                    return
                subject_id = int(subject_value)
                data = _build_subject_study(subject_id)
                if data.get("ok"):
                    reviews = _build_subject_reviews(subject_id)
                    data["reviews"] = reviews if reviews.get("ok") else None
                self._send_json(data, 200 if data.get("ok") else 400)
                return

            if parsed.path.startswith("/api/subjects/") and parsed.path.endswith("/knowledge"):
                path_parts = parsed.path.strip("/").split("/")
                if len(path_parts) != 4:
                    self._send_json({"ok": False, "error": "Ruta de conocimiento inválida"}, 404)
                    return
                subject_id = int(path_parts[2])
                data = build_subject_knowledge_map(subject_id)
                self._send_json(data, 200 if data.get("ok") else 404)
                return

            self._send_json({"ok": False, "error": "Ruta no encontrada"}, 404)

        except ValueError:
            self._send_json({"ok": False, "error": "Parámetro numérico inválido"}, 400)
        except Exception as exc:
            self._send_json({
                "ok": False,
                "error": f"Error interno de la API local: {type(exc).__name__}: {exc}",
            }, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/agent/message":
                payload = self._read_json()
                message = str(payload.get("message", "")).strip()
                if not message:
                    self._send_json({"ok": False, "error": "Escribe un mensaje para UniCore"}, 400)
                    return
                runtime_context = build_runtime_context(
                    conversation_id=payload.get("conversation_id"),
                    allow_writes=False,
                )
                agent = UniCoreAgent(
                    maximum_steps=4,
                    maximum_output_tokens=600,
                    runtime_context=runtime_context,
                )
                result = asyncio.run(agent.run(message))
                response = {
                    "ok": bool(result.get("ok")),
                    "answer": result.get("answer"),
                    "status": result.get("status", "completed" if result.get("ok") else "error"),
                    "conversation_id": runtime_context.conversation_id,
                    "error": result.get("error"),
                }
                job = result.get("job")
                if isinstance(job, dict):
                    response["job"] = {
                        "status": job.get("status"),
                        "kind": job.get("kind"),
                        "objective": job.get("objective"),
                        "created_at": job.get("created_at"),
                    }
                self._send_json(response, 200 if response["ok"] else 502)
                return
            self._send_json({"ok": False, "error": "Ruta no encontrada"}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, 400)
        except Exception:
            self._send_json({"ok": False, "error": "UniCore Agent no pudo completar la solicitud"}, 500)

    def log_message(self, format, *args):
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), UniCoreFrontendAPIHandler)
    print()
    print("UniCore Frontend API")
    print("====================")
    print()
    print(f"API: http://{HOST}:{PORT}")
    print("Health: /api/health")
    print("Dashboard: /api/dashboard")
    print("Decision plan: /api/decision-plan")
    print()
    print("Ctrl + C para detener.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print()
        print("API detenida.")


if __name__ == "__main__":
    main()
