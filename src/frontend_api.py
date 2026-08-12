import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.decision_engine import build_decision_plan
from src.mcp_resources import _build_tasks
from src.unicore_dashboard import build_dashboard_data

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
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._allowed_origin())
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

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

            self._send_json({"ok": False, "error": "Ruta no encontrada"}, 404)

        except ValueError:
            self._send_json({"ok": False, "error": "Parámetro numérico inválido"}, 400)
        except Exception as exc:
            self._send_json({
                "ok": False,
                "error": f"Error interno de la API local: {type(exc).__name__}: {exc}",
            }, 500)

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
