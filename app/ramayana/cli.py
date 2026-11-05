"""Command-line retrieval entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .store import VerseStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the local Ramayana index")
    parser.add_argument("query")
    parser.add_argument("--database", type=Path, default=Path("data/ramayana.sqlite3"))
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    store = VerseStore(args.database)
    try:
        results = store.search(args.query, max(1, min(args.limit, 20)))
    finally:
        store.close()

    if not results:
        print("No indexed verses matched this question.")
        return
    for result in results:
        print(f"[{result['book']} | Sarga {result['sarga']} | Verse {result['verse_id']}]\n")
        print(result["prose"] or result["gloss"] or result["devanagari"])
        print(f"Source: {result['source_path']} ({result['source_edition']})\n")


if __name__ == "__main__":
    main()
