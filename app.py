from __future__ import annotations

import argparse
import json
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any

from engine import LaboralEngine


APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"
DEFAULT_DATA_FILE = APP_ROOT / "data" / "convenio_acuaticas_2025_2027.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PGK Laboral Desk demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-file", default=str(DEFAULT_DATA_FILE))
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    engine = LaboralEngine.from_json_file(args.data_file)
    handler = build_handler(STATIC_DIR, engine)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"

    print(f"PGK Laboral Desk disponible en {url}")
    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def build_handler(static_dir: Path, engine: LaboralEngine) -> type[SimpleHTTPRequestHandler]:
    class AppHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def do_GET(self) -> None:
            request_path = urlsplit(self.path).path
            if request_path == "/api/health":
                self._send_json({"ok": True})
                return
            if request_path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:
            if self.path != "/api/analyze":
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            query = str(payload.get("query", "")).strip()
            if not query:
                self._send_json({"error": "La consulta no puede estar vacia."}, status=HTTPStatus.BAD_REQUEST)
                return

            result = engine.analyze(query)
            self._send_json(result)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.end_headers()
            self.wfile.write(body)

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

    return AppHandler


if __name__ == "__main__":
    raise SystemExit(main())
