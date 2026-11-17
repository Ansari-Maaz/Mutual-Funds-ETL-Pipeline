from datetime import date
from decimal import Decimal

from app.holdings.sec_nmfp_bulk import _decimal, _holdings_rows, _rows, _sec_date


def test_nmfp_sec_date_parses_sec_month_format():
    assert _sec_date("31-AUG-2026") == date(2026, 8, 31)
    assert _sec_date("2026-08-31") == date(2026, 8, 31)
    assert _sec_date("") is None


def test_nmfp_decimal_handles_padded_and_blank_values():
    assert _decimal("   1.0001") == Decimal("1.0001")
    assert _decimal("N/A") is None
    assert _decimal("") is None


def test_nmfp_holdings_only_reads_requested_accessions_and_scales_percentage(tmp_path):
    header = ("ACCESSION_NUMBER\tSECURITY_ID\tNAMEOFISSUER\tTITLEOFISSUER\tCUSIP_NUMBER\t"
              "ISIN\tPERCENTAGEOFMONEYMARKETFUNDNET\n")
    body = (
        "acc-1\t1\tISSUER A\tTREASURY 2026\t912797TC1\tUS912797TC16\t.0048\n"
        "acc-2\t1\tISSUER B\tOTHER\t\t\t.5\n"
    )
    path = tmp_path / "NMFP_SCHPORTFOLIOSECURITIES.tsv"
    path.write_text(header + body, encoding="utf-8")

    rows = _holdings_rows(tmp_path, {"acc-1"})

    assert set(rows) == {"acc-1"}
    holding = rows["acc-1"][0]
    assert holding["security_name"] == "TREASURY 2026"
    assert holding["cusip"] == "912797TC1"
    assert holding["isin"] == "US912797TC16"
    # SEC reports the percentage as a fraction of net assets.
    assert holding["portfolio_weight"] == Decimal("0.48")


def test_nmfp_rows_strips_header_only_reader(tmp_path):
    path = tmp_path / "sample.tsv"
    path.write_text("A\tB\n1\t2\n", encoding="utf-8")
    assert list(_rows(path)) == [{"A": "1", "B": "2"}]
