"""Corpus ingestion command for the local SQLite index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .parsers import iter_corpus_records
from .store import VerseStore


def ingest(root: Path, database: Path, dry_run: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    records = iter_corpus_records(root)
    store = None if dry_run else VerseStore(database)
    total = 0
    try:
        for record in records:
            counts[record.source_edition] = counts.get(record.source_edition, 0) + 1
            total += 1
            if store is not None:
                store.add(record)
        if store is not None:
            store.connection.commit()
    finally:
        if store is not None:
            store.close()
    return {"total": total, **counts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Index local Valmiki Ramayana datasets")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--database", type=Path, default=Path("data/ramayana.sqlite3"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(ingest(args.root, args.database, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
