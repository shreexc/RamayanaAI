from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))

from ramayana.parsers import dataset_one_records, dataset_two_records


ROOT = Path(__file__).parents[1]


def test_dataset_one_preserves_ids_and_text():
    records = dataset_one_records(ROOT / "dataset-1" / "Ram01.txt")

    assert records
    assert records[0].book == "Bala Kanda"
    assert records[0].verse_id == "1-1-1"
    assert "तपःस्वाध्यायनिरतं" in records[0].devanagari
    assert records[0].source_edition == "dataset-1"


def test_dataset_two_extracts_structured_context():
    path = ROOT / "dataset-2" / "utf8" / "ayodhya" / "sarga1" / "ayodhyasans1.htm"
    records = dataset_two_records(path)

    assert records
    assert records[0].book == "Ayodhya Kanda"
    assert records[0].sarga == "1"
    assert records[0].verse_id == "2-1-1"
    assert "गच्छता मातुलकुलं" in records[0].devanagari
    assert records[0].gloss
    assert records[0].prose
    assert records[0].source_edition == "dataset-2-sanskrit"


def test_frame_pages_are_excluded():
    path = ROOT / "dataset-2" / "ayodhya" / "sarga2" / "ayodhya_2_frame.htm"

    assert dataset_two_records(path) == []
