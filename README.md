# Local Ramayana Chat

A local-only retrieval assistant for the Valmiki Ramayana corpus. It currently parses Dataset 1 and canonical UTF-8 Dataset 2 pages, stores verse records in SQLite FTS5, and serves a localhost browser chat. Ollama generation is optional; when Ollama is unavailable, the service returns the retrieved passages directly.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Build the local index

A dry run only counts recognized records:

```bash
PYTHONPATH=app .venv/bin/python -m ramayana.ingest --root . --dry-run
```

Create or refresh the SQLite index:

```bash
PYTHONPATH=app .venv/bin/python -m ramayana.ingest --root . --database data/ramayana.sqlite3
```

## Run the local chat

```bash
PYTHONPATH=app .venv/bin/python -m ramayana.server
```

Open <http://127.0.0.1:8000> in a browser. The service binds to localhost only.

The CLI is also available:

```bash
PYTHONPATH=app .venv/bin/python -m ramayana.cli "What virtues of Rama are described?"
```

## Optional semantic retrieval

After the Ollama daemon is running and `nomic-embed-text` is available, add embeddings in small resumable runs. The default processes only 500 new records so CPU and memory stay bounded:

```bash
ollama pull nomic-embed-text
PYTHONPATH=app .venv/bin/python -m ramayana.embed --database data/ramayana.sqlite3 --max-records 500
```

Repeat the command to continue. Use a larger explicit `--max-records` only while monitoring system memory. The API automatically combines embeddings with FTS5 when embeddings exist and falls back to FTS5 otherwise.

## Optional Ollama generation

Install Ollama using the official Fedora/Linux instructions, start its local service, and pull a small quantized model:

```bash
ollama pull qwen2.5:1.5b
```

The server uses `qwen2.5:1.5b` by default for CPU responsiveness and sends it only retrieved evidence. Override the model or endpoint without editing code:

```bash
OLLAMA_MODEL=qwen2.5:1.5b OLLAMA_URL=http://127.0.0.1:11434 PYTHONPATH=app .venv/bin/python -m ramayana.server
```

No cloud API, remote vector store, or automatic fallback is used.

## Tests

```bash
.venv/bin/pytest -q
```

The fixed retrieval evaluation can be run with:

```bash
PYTHONPATH=app .venv/bin/python -m ramayana.evaluate
```
# RamayanaAI
