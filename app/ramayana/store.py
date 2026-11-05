"""SQLite storage and lightweight lexical retrieval."""

from __future__ import annotations

import sqlite3
import re
import math
import struct
from dataclasses import asdict
from pathlib import Path

from .parsers import VerseRecord


STOP_WORDS = {"a", "an", "and", "are", "be", "described", "for", "how", "is", "of", "the", "to", "what", "when", "who"}


SCHEMA = """
CREATE TABLE IF NOT EXISTS verses (
    id INTEGER PRIMARY KEY,
    book TEXT NOT NULL,
    sarga TEXT NOT NULL,
    verse_id TEXT NOT NULL,
    devanagari TEXT NOT NULL DEFAULT '',
    roman TEXT NOT NULL DEFAULT '',
    itrans TEXT NOT NULL DEFAULT '',
    gloss TEXT NOT NULL DEFAULT '',
    prose TEXT NOT NULL DEFAULT '',
    source_path TEXT NOT NULL,
    source_edition TEXT NOT NULL,
    UNIQUE(verse_id, source_path, source_edition)
);
CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
    book, sarga, verse_id, devanagari, roman, itrans, gloss, prose,
    content='verses', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS verses_ai AFTER INSERT ON verses BEGIN
    INSERT INTO verses_fts(rowid, book, sarga, verse_id, devanagari, roman, itrans, gloss, prose)
    VALUES (new.id, new.book, new.sarga, new.verse_id, new.devanagari, new.roman, new.itrans, new.gloss, new.prose);
END;
CREATE TRIGGER IF NOT EXISTS verses_ad AFTER DELETE ON verses BEGIN
    INSERT INTO verses_fts(verses_fts, rowid, book, sarga, verse_id, devanagari, roman, itrans, gloss, prose)
    VALUES ('delete', old.id, old.book, old.sarga, old.verse_id, old.devanagari, old.roman, old.itrans, old.gloss, old.prose);
END;
CREATE TABLE IF NOT EXISTS embeddings (
    verse_rowid INTEGER PRIMARY KEY REFERENCES verses(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    vector BLOB NOT NULL,
    dimensions INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class VerseStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def add(self, record: VerseRecord) -> None:
        values = asdict(record)
        self.connection.execute(
            """
            INSERT INTO verses (
                book, sarga, verse_id, devanagari, roman, itrans, gloss, prose,
                source_path, source_edition
            ) VALUES (
                :book, :sarga, :verse_id, :devanagari, :roman, :itrans, :gloss, :prose,
                :source_path, :source_edition
            )
            ON CONFLICT(verse_id, source_path, source_edition) DO UPDATE SET
                book=excluded.book, sarga=excluded.sarga, devanagari=excluded.devanagari,
                roman=excluded.roman, itrans=excluded.itrans, gloss=excluded.gloss,
                prose=excluded.prose
            """,
            values,
        )

    def add_many(self, records: list[VerseRecord]) -> int:
        for record in records:
            self.add(record)
        self.connection.commit()
        return len(records)

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM verses").fetchone()[0])

    def embedding_count(self, model: str) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM embeddings WHERE model = ?", (model,)).fetchone()[0])

    def embedding_rows(self, model: str, limit: int | None = None):
        query = """
            SELECT verses.*, embeddings.vector, embeddings.dimensions
            FROM embeddings JOIN verses ON verses.id = embeddings.verse_rowid
            WHERE embeddings.model = ? ORDER BY verses.id
        """
        params: list[object] = [model]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        return self.connection.execute(query, params).fetchall()

    def save_embedding(self, verse_rowid: int, model: str, vector: list[float]) -> None:
        packed = struct.pack(f"<{len(vector)}f", *vector)
        self.connection.execute(
            """
            INSERT INTO embeddings (verse_rowid, model, vector, dimensions)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(verse_rowid) DO UPDATE SET model=excluded.model,
                vector=excluded.vector, dimensions=excluded.dimensions,
                updated_at=CURRENT_TIMESTAMP
            """,
            (verse_rowid, model, packed, len(vector)),
        )

    @staticmethod
    def _unpack(vector: bytes, dimensions: int) -> list[float]:
        return list(struct.unpack(f"<{dimensions}f", vector))

    def search_hybrid(self, query: str, query_vector: list[float] | None = None, limit: int = 8, model: str = "") -> list[dict[str, str]]:
        lexical = self.search(query, limit=max(limit * 5, 20))
        if not query_vector or not model:
            return lexical[:limit]
        query_norm = math.sqrt(sum(value * value for value in query_vector)) or 1.0
        scored: list[tuple[float, sqlite3.Row]] = []
        lexical_ids = {item["id"] for item in lexical}
        for row in self.embedding_rows(model):
            vector = self._unpack(row["vector"], row["dimensions"])
            if len(vector) != len(query_vector):
                continue
            score = sum(left * right for left, right in zip(vector, query_vector))
            score /= query_norm * (math.sqrt(sum(value * value for value in vector)) or 1.0)
            if row["id"] in lexical_ids:
                score += 0.15
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [{key: row[key] for key in row.keys() if key not in {"vector", "dimensions"}} for _, row in scored[:limit]]

    def search_diverse(self, query: str, query_vector: list[float] | None = None, limit: int = 6, model: str = "") -> list[dict[str, str]]:
        ranked = self.search_hybrid(query, query_vector, limit=max(limit * 3, 18), model=model)
        selected: list[dict[str, str]] = []
        seen: set[int] = set()

        def add(item: dict[str, str]) -> None:
            if item["id"] not in seen and len(selected) < limit:
                seen.add(item["id"])
                selected.append(item)

        for item in ranked[:limit]:
            add(item)
            counterparts = self.connection.execute(
                "SELECT * FROM verses WHERE verse_id = ? AND source_edition != ? ORDER BY source_edition",
                (item["verse_id"], item["source_edition"]),
            ).fetchall()
            for counterpart in counterparts:
                add(dict(counterpart))
        for item in ranked:
            add(item)
        return selected

    def search(self, query: str, limit: int = 8) -> list[dict[str, str]]:
        exact_ids = re.findall(r"\d+-\d+-\d+", query)
        tokens = [part for part in re.findall(r"[\w\u0900-\u097f]+", query, re.UNICODE) if part.lower() not in STOP_WORDS]
        terms = " OR ".join(f'"{part.replace(chr(34), "")}"' for part in tokens)
        exact_rows = []
        if exact_ids:
            placeholders = ",".join("?" for _ in exact_ids)
            exact_rows = self.connection.execute(
                f"SELECT * FROM verses WHERE verse_id IN ({placeholders}) LIMIT ?",
                (*exact_ids, limit),
            ).fetchall()
        if not terms and not exact_rows:
            return []
        rows = [] if not terms else self.connection.execute(
            """
            SELECT verses.*
            FROM verses_fts
            JOIN verses ON verses.id = verses_fts.rowid
            WHERE verses_fts MATCH ?
            ORDER BY bm25(verses_fts)
            LIMIT ?
            """,
            (terms, limit),
        ).fetchall()
        scored_rows = []
        for row in rows:
            searchable = " ".join(str(row[column]) for column in ("book", "verse_id", "devanagari", "roman", "itrans", "gloss", "prose")).lower()
            score = sum(searchable.count(token.lower()) for token in tokens)
            scored_rows.append((score, row))
        scored_rows.sort(key=lambda item: item[0], reverse=True)
        seen = set()
        ordered = []
        for row in (*exact_rows, *(row for _, row in scored_rows)):
            if row["id"] not in seen:
                seen.add(row["id"])
                ordered.append(dict(row))
        return ordered[:limit]
