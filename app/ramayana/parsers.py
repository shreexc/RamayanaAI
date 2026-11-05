"""Corpus parsers for the two local Valmiki Ramayana datasets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup


BOOK_NAMES = {
    "01": "Bala Kanda",
    "02": "Ayodhya Kanda",
    "03": "Aranya Kanda",
    "04": "Kishkindha Kanda",
    "05": "Sundara Kanda",
    "06": "Yuddha Kanda",
    "07": "Uttara Kanda",
}

VERSE_ID_RE = re.compile(r"([0-9०-९]+\s*[-.]\s*[0-9०-९]+\s*[-.]\s*[0-9०-९]+)")
DATASET_ONE_ID_RE = re.compile(r"^(\d{7})([a-z])$")
DIGIT_TRANSLATION = str.maketrans("०१२३४५६७८९", "0123456789")


@dataclass(frozen=True)
class VerseRecord:
    book: str
    sarga: str
    verse_id: str
    devanagari: str = ""
    roman: str = ""
    itrans: str = ""
    gloss: str = ""
    prose: str = ""
    source_path: str = ""
    source_edition: str = ""

    @property
    def search_text(self) -> str:
        return " ".join(
            value
            for value in (
                self.book,
                self.sarga,
                self.verse_id,
                self.devanagari,
                self.roman,
                self.itrans,
                self.gloss,
                self.prose,
            )
            if value
        )


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def normalize_verse_id(value: str) -> str:
    value = value.translate(DIGIT_TRANSLATION)
    value = re.sub(r"\s*[-.]\s*", "-", value)
    return value


def dataset_one_records(path: Path) -> list[VerseRecord]:
    book_match = re.search(r"Ram(\d{2})", path.name, re.IGNORECASE)
    book = BOOK_NAMES.get(book_match.group(1), path.stem) if book_match else path.stem
    grouped: dict[str, list[str]] = {}

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = DATASET_ONE_ID_RE.match(line.strip().split(maxsplit=1)[0] if line.strip() else "")
        if not match:
            continue
        compact_id, pada = match.groups()
        kanda = int(compact_id[0])
        sarga = int(compact_id[1:4])
        verse_number = int(compact_id[4:7])
        verse_id = f"{kanda}-{sarga}-{verse_number}"
        grouped.setdefault(verse_id, []).append(clean_text(line.strip()[len(match.group(0)) :]))
    return [
        VerseRecord(
            book=book,
            sarga=verse_id.split("-")[1],
            verse_id=verse_id,
            devanagari=" | ".join(padas),
            source_path=str(path),
            source_edition="dataset-1",
        )
        for verse_id, padas in grouped.items()
    ]


def _page_metadata(path: Path, soup: BeautifulSoup) -> tuple[str, str]:
    title = clean_text(soup.title.get_text(" ") if soup.title else "")
    book_match = re.search(r"-\s*([^:-]+Kanda)\s*-", title, re.IGNORECASE)
    sarga_match = re.search(r"(?:Sarga|Chapter)[^0-9०-९]*([0-9०-९]+)", title, re.IGNORECASE)
    book = clean_text(book_match.group(1)) if book_match else path.parent.parent.name
    sarga = sarga_match.group(1).translate(DIGIT_TRANSLATION) if sarga_match else path.parent.name.removeprefix("sarga")
    return book, sarga


def _first_verse_id(text: str) -> str:
    match = VERSE_ID_RE.search(text)
    return normalize_verse_id(match.group(1)) if match else ""


def dataset_two_records(path: Path) -> list[VerseRecord]:
    if path.suffix.lower() not in {".htm", ".html"}:
        return []
    lowered = path.name.lower()
    if any(marker in lowered for marker in ("_frame", "index", ".orig.", ".bad.", ".old.")):
        return []

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    verse_class = next(
        (class_name for class_name in ("SanSloka", "RomSloka", "ItrSloka") if soup.select_one(f"p.{class_name}")),
        None,
    )
    if verse_class is None:
        return []

    book, sarga = _page_metadata(path, soup)
    edition = {"SanSloka": "dataset-2-sanskrit", "RomSloka": "dataset-2-roman", "ItrSloka": "dataset-2-itrans"}[verse_class]
    records: list[VerseRecord] = []
    for verse in soup.select(f"p.{verse_class}"):
        verse_text = clean_text(verse.get_text(" "))
        verse_id = _first_verse_id(verse_text)
        if not verse_id:
            continue
        following = verse.find_all_next(["p"], limit=3)
        gloss = next((clean_text(node.get_text(" ")) for node in following if "pratipada" in (node.get("class") or [])), "")
        prose = next((clean_text(node.get_text(" ")) for node in following if "tat" in (node.get("class") or [])), "")
        records.append(
            VerseRecord(
                book=book,
                sarga=sarga,
                verse_id=verse_id,
                devanagari=verse_text if verse_class == "SanSloka" else "",
                roman=verse_text if verse_class == "RomSloka" else "",
                itrans=verse_text if verse_class == "ItrSloka" else "",
                gloss=gloss,
                prose=prose,
                source_path=str(path),
                source_edition=edition,
            )
        )
    return records


def iter_corpus_records(root: Path) -> Iterable[VerseRecord]:
    dataset_one = root / "dataset-1"
    for path in sorted(dataset_one.glob("Ram*.txt")):
        yield from dataset_one_records(path)

    utf8_root = root / "dataset-2" / "utf8"
    for path in sorted(utf8_root.rglob("*.htm")):
        yield from dataset_two_records(path)
    for path in sorted(utf8_root.rglob("*.html")):
        yield from dataset_two_records(path)
