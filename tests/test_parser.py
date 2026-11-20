import pytest
from scheduler.parser import normalize_text, parse_blocked_sessions_text, match_dosen
from scheduler.models import Dosen

def test_normalize_text():
    assert normalize_text("Maryo Inri Pratama (MAR)") == "inri maryo pratama"
    assert normalize_text("Kaulika Putri Anjani") == "anjani kaulika putri"
    assert normalize_text("Kaulika Anjani Putri (KAP)") == "anjani kaulika putri"

def test_match_dosen():
    d1 = Dosen(id=3, name="Maryo Inri Pratama (MAR)", code="MAR")
    d2 = Dosen(id=12, name="Kaulika Anjani Putri (KAP)", code="KAP")
    dosen_map = {
        normalize_text(d1.name): d1,
        normalize_text(d2.name): d2,
    }

    # Exact token match
    assert match_dosen("Maryo Inri Pratama", dosen_map) == d1
    # Subset token match
    assert match_dosen("Maryo Inri", dosen_map) == d1
    # Swapped words
    assert match_dosen("Kaulika Putri Anjani", dosen_map) == d2

def test_parse_blocked_sessions_text():
    # Full day keywords
    res, warn = parse_blocked_sessions_text("Latsar")
    assert res == {1, 2, 3, 4}
    assert warn is None

    res, warn = parse_blocked_sessions_text("Survei Riset")
    assert res == {1, 2, 3, 4}
    assert warn is None

    # Range
    res, warn = parse_blocked_sessions_text("Sesi 1-4")
    assert res == {1, 2, 3, 4}
    assert warn is None

    res, warn = parse_blocked_sessions_text("sesi 2 - 3")
    assert res == {2, 3}
    assert warn is None

    # Comma or list
    res, warn = parse_blocked_sessions_text("Sesi 1, 3")
    assert res == {1, 3}
    assert warn is None

    res, warn = parse_blocked_sessions_text("sesi 2, 4")
    assert res == {2, 4}
    assert warn is None

    # Unknown text emits warning
    res, warn = parse_blocked_sessions_text("izin acara keluarga")
    assert res == set()
    assert warn is not None
