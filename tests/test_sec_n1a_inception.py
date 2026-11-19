"""Tests for the N-1A prospectus inception extractor."""
from __future__ import annotations

from datetime import date

from app.enrichment import sec_n1a_inception as n1a

TEXT = (
    "Class A shares of the Fund commenced operations on January 2, 2019. "
    "Class C shares commenced operations on August 14, 2015. "
    "Institutional Class commenced operations as of June 30, 2011. "
    "The Fund has not commenced operations as of the date of this prospectus. "
    "The Alpha Fund has been in operation since June 30, 2011.")


def test_find_candidates_keeps_full_dates_only():
    candidates = n1a.find_candidates(TEXT)
    dates = {item["date"] for item in candidates}
    assert date(2019, 1, 2) in dates and date(2015, 8, 14) in dates
    assert all(len(item["snippet"]) <= 400 for item in candidates)
    # A negative statement ("has not commenced") is never a candidate.
    assert not any("has not commenced" in item["snippet"].lower()
                   and item["pattern"] == "commenced_operations" for item in candidates)


def test_class_statement_wins_over_series_statement():
    choice = n1a.resolve(n1a.find_candidates(TEXT), class_name="Class C",
                         series_name="Alpha Fund", single_class=False, filed=date(2026, 1, 1))
    assert choice["date"] == date(2015, 8, 14)
    assert choice["scope"] == "share_class"


def test_series_statement_applies_only_to_single_class_series():
    candidates = n1a.find_candidates(TEXT)
    single = n1a.resolve(candidates, class_name="Unlisted Shares",
                         series_name="Alpha Fund", single_class=True, filed=date(2026, 1, 1))
    multi = n1a.resolve(candidates, class_name="Unlisted Shares",
                        series_name="Alpha Fund", single_class=False, filed=date(2026, 1, 1))
    assert single["scope"] == "series" and single["date"] == date(2011, 6, 30)
    assert multi is None


def test_other_fund_statement_is_not_attributed():
    text = "The Beta Fund commenced operations on May 30, 2024."
    assert n1a.resolve(n1a.find_candidates(text), class_name="Class A",
                       series_name="Alpha Fund", single_class=True, filed=date(2026, 1, 1)) is None


def test_date_after_filing_is_rejected():
    text = "Class A commenced operations on January 2, 2027."
    assert n1a.resolve(n1a.find_candidates(text), class_name="Class A",
                       series_name="Alpha Fund", single_class=False, filed=date(2026, 1, 1)) is None


def test_archive_key_orders_quarters_and_months():
    from pathlib import Path
    names = [Path(n) for n in ("2025q4_rr1.zip", "2026-10_rr1.zip", "2026q1_rr1.zip")]
    assert sorted(names, key=n1a._archive_key, reverse=True) == [
        Path("2026-10_rr1.zip"), Path("2026q1_rr1.zip"), Path("2025q4_rr1.zip")]
