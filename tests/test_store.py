from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))

from ramayana.parsers import VerseRecord
from ramayana.store import VerseStore


def test_diverse_search_adds_same_verse_from_other_edition(tmp_path: Path):
    store = VerseStore(tmp_path / "test.sqlite3")
    try:
        store.add_many([
            VerseRecord(
                book="Bala Kanda", sarga="1", verse_id="1-1-1",
                devanagari="रामः", source_path="dataset-1/Ram01.txt", source_edition="dataset-1",
            ),
            VerseRecord(
                book="Bala Kanda", sarga="1", verse_id="1-1-1",
                roman="Rama", prose="Rama is described.", source_path="dataset-2/utf8/baala/sarga1/page.htm", source_edition="dataset-2-sanskrit",
            ),
        ])
        results = store.search_diverse("1-1-1", limit=2)
    finally:
        store.close()

    assert {result["source_edition"] for result in results} == {"dataset-1", "dataset-2-sanskrit"}
