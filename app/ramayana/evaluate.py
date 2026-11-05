"""Small offline retrieval evaluation for the local corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .store import VerseStore


def evaluate(database: Path, questions_path: Path, limit: int) -> dict[str, object]:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    store = VerseStore(database)
    results = []
    try:
        for item in questions:
            matches = store.search(item["question"], limit=limit)
            haystack = " ".join(json.dumps(match, ensure_ascii=False) for match in matches).lower()
            found = [term for term in item["expected_terms"] if term.lower() in haystack]
            results.append({"question": item["question"], "found": found, "expected": item["expected_terms"], "passed": len(found) == len(item["expected_terms"])})
    finally:
        store.close()
    passed = sum(1 for result in results if result["passed"])
    return {"passed": passed, "total": len(results), "accuracy": passed / len(results) if results else 0, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate lexical retrieval against fixed questions")
    parser.add_argument("--database", type=Path, default=Path("data/ramayana.sqlite3"))
    parser.add_argument("--questions", type=Path, default=Path("evaluation/questions.json"))
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.database, args.questions, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
