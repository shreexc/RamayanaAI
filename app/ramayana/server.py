"""Local HTTP API and browser host for the Ramayana assistant."""

from __future__ import annotations

import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .store import VerseStore
from .ollama_client import embed_text, generate


ROOT = Path(__file__).parents[2]
STATIC_ROOT = ROOT / "app" / "static"
DATABASE = Path(os.environ.get("RAMAYANA_DATABASE", ROOT / "data" / "ramayana.sqlite3"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def ollama_answer(question: str, evidence: list[dict[str, str]]) -> str | None:
    context = "\n\n".join(
        f"[{item['source_edition']} | {item['book']} | Sarga {item['sarga']} | Verse {item['verse_id']}]\n"
        f"Sanskrit: {item['devanagari'][:500]}\n"
        f"Roman/ITRANS: {(item['roman'] or item['itrans'])[:500]}\n"
        f"Gloss: {item['gloss'][:500]}\n"
        f"English: {item['prose'][:700]}"
        for item in evidence
    )
    context = context[:5000]
    prompt = (
        "You answer questions about the Valmiki Ramayana. Use only the supplied evidence. "
        "If the evidence does not answer the question, say so plainly. Keep the answer concise "
        "and cite the verse identifiers and source edition in square brackets. Treat Dataset 1 "
        "and Dataset 2 as separate editions; compare them when both are supplied and do not invent "
        "a translation for Sanskrit-only evidence. Answer the question directly; do not define "
        "every glossary token, call Dataset 1 translated, or invent meanings that are not needed "
        "to answer it.\n\n"
        f"Question: {question}\n\nEvidence:\n{context}"
    )
    return generate(prompt, OLLAMA_MODEL, max_tokens=128)


def direct_verse_answer(question: str, evidence: list[dict[str, str]]) -> str | None:
    verse_ids = re.findall(r"\d+-\d+-\d+", question)
    if not verse_ids:
        return None
    for item in evidence:
        if item["verse_id"] in verse_ids and item["prose"]:
            return f"Verse {item['verse_id']}: {item['prose']} [{item['source_edition']}]"
    return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: HTTPStatus, body: object, content_type: str = "application/json") -> None:
        encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except BrokenPipeError:
            return

    def do_GET(self) -> None:
        if self.path == "/api/health":
            store = VerseStore(DATABASE)
            try:
                count = store.count()
                embedded = store.embedding_count(OLLAMA_EMBED_MODEL)
            finally:
                store.close()
            self._send(HTTPStatus.OK, {"ok": True, "indexed_verses": count, "embedded_verses": embedded, "ollama_model": OLLAMA_MODEL, "embedding_model": OLLAMA_EMBED_MODEL})
            return
        if self.path in {"/", "/index.html"}:
            self._send(HTTPStatus.OK, (STATIC_ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(min(size, 32_000)))
            question = str(payload.get("question", "")).strip()
        except (ValueError, json.JSONDecodeError):
            self._send(HTTPStatus.BAD_REQUEST, {"error": "Request must contain JSON."})
            return
        if not question:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "Question is required."})
            return

        store = VerseStore(DATABASE)
        try:
            query_vector = embed_text(question, OLLAMA_EMBED_MODEL) if store.embedding_count(OLLAMA_EMBED_MODEL) else None
            evidence = store.search_diverse(question, query_vector, limit=3, model=OLLAMA_EMBED_MODEL)
        finally:
            store.close()
        if not evidence:
            self._send(HTTPStatus.OK, {"answer": "I could not find supporting verses in the indexed corpus.", "sources": []})
            return

        answer = direct_verse_answer(question, evidence) or ollama_answer(question, evidence)
        if answer is None:
            answer = "I found these relevant passages. Ollama is not available, so I am showing the retrieved evidence directly."
        self._send(HTTPStatus.OK, {"answer": answer, "sources": evidence})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    port = int(os.environ.get("RAMAYANA_PORT", "8000"))
    server = None
    for candidate in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            port = candidate
            break
        except OSError as error:
            if error.errno != 98 or candidate == port + 9:
                raise
    print(f"Ramayana chat running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
