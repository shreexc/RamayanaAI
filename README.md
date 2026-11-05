# Local Ramayana Chat

It is based on the foundation of ollama, the dataset used are the original scriptures of Ramayana taken from Vedic websites, the chatbot is capable of running locally and with unlimited questions. This entire project is the product of "Agentic coding" which has been far more feasible and faster to train and create AIs. However, for the authenticity and less hallucinations the RAG model only answers via the datasets provided, and its results might vary from the stories you heard but whatever it answers comes straight from the scriptures and the bot also provides evidences in the right panel (from the scriptures).

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
# RamayanaAI
