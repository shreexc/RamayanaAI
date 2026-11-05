"""Resumable, single-worker Ollama embedding job."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ollama_client import embed_text
from .store import VerseStore


def run(database: Path, model: str, max_records: int, commit_every: int) -> dict[str, int | str]:
    store = VerseStore(database)
    processed = 0
    skipped = 0
    try:
        rows = store.connection.execute(
            """
            SELECT verses.* FROM verses
            LEFT JOIN embeddings ON embeddings.verse_rowid = verses.id AND embeddings.model = ?
            WHERE embeddings.verse_rowid IS NULL ORDER BY verses.id LIMIT ?
            """,
            (model, max_records),
        ).fetchall()
        for row in rows:
            text = " ".join(
                value for value in (
                    row["book"], row["sarga"], row["verse_id"], row["devanagari"],
                    row["roman"], row["itrans"], row["gloss"], row["prose"],
                ) if value
            )
            vector = embed_text(text, model)
            if not vector:
                skipped += 1
                continue
            store.save_embedding(row["id"], model, vector)
            processed += 1
            if processed % commit_every == 0:
                store.connection.commit()
                print(json.dumps({"processed": processed, "skipped": skipped}), flush=True)
        store.connection.commit()
        return {"model": model, "processed": processed, "skipped": skipped, "total_for_model": store.embedding_count(model)}
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create local Ollama embeddings safely and resumably")
    parser.add_argument("--database", type=Path, default=Path("data/ramayana.sqlite3"))
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--max-records", type=int, default=500, help="Maximum new embeddings in this run")
    parser.add_argument("--commit-every", type=int, default=10)
    args = parser.parse_args()
    if args.max_records < 1 or args.commit_every < 1:
        parser.error("--max-records and --commit-every must be positive")
    print(json.dumps(run(args.database, args.model, args.max_records, args.commit_every), indent=2))


if __name__ == "__main__":
    main()
