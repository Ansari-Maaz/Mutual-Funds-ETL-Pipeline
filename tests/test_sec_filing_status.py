"""Tests for the SEC reporting-status observation helper."""
from __future__ import annotations

from datetime import date

from app.enrichment import sec_filing_status as status


def test_months_before_crosses_year_boundary():
    assert status._months_before(date(2026, 10, 31), 12) == date(2025, 10, 28)
    assert status._months_before(date(2026, 2, 15), 3) == date(2025, 11, 15)


def test_date_parses_every_sec_layout():
    assert status._date("2026-05-31") == date(2026, 5, 31)
    assert status._date("31-MAY-2026") == date(2026, 5, 31)
    assert status._date("05/31/2026") == date(2026, 5, 31)
    assert status._date("20260531") == date(2026, 5, 31)
    assert status._date("") is None


def test_rows_tolerate_missing_archive(tmp_path):
    assert list(status._rows(tmp_path / "absent.tsv")) == []
