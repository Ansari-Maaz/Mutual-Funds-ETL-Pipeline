import io
import zipfile
from datetime import date
from decimal import Decimal

from app.enrichment import sec_rr_profile as rr

SUB = "adsh\tfiled\nA-1\t20250105\nA-2\t20251120\n"
TXT_HEAD = "adsh\ttag\tversion\tddate\tqtrs\tseries\tclass\tmeasure\tdocument\totherdims\tlang\tvalue\n"
SCN = "adsh\tseriesid\tseriesname\tclassid\tclassname\tticker\n"
NUM_HEAD = ("adsh\ttag\tversion\tddate\tqtrs\tuom\tseries\tclass\tmeasure\tdocument\totherdims"
            "\tiprx\tvalue\tfootnote\tfootlen\tdimn\tdcml\n")


def make_archive(tmp_path, txt_rows, scn_rows, num_rows=None):
    path = tmp_path / "2025q4_rr1.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("sub.tsv", SUB)
        bundle.writestr("txt.tsv", TXT_HEAD + "".join(txt_rows))
        bundle.writestr("scn.tsv", SCN + "".join(scn_rows))
        if num_rows is not None:
            bundle.writestr("num.tsv", NUM_HEAD + "".join(num_rows))
    return path


def test_available_archives_reads_supported_layouts_newest_first(monkeypatch):
    html = ('<a href="/files/dera/data/x/2023_rr1.zip">'
            '<a href="/files/dera/data/x/2025q4_rr1.zip"><a href="/files/dera/data/x/2026-10_rr1.zip">'
            '<a href="/files/dera/data/x/2026q3_rr1.zip">')

    class Response:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return html.encode()

    monkeypatch.setattr(rr.urllib.request, "urlopen", lambda *a, **k: Response())
    assert rr.available_archives() == ["2026-10", "2026q3", "2025q4", "2023"]
    assert rr.available_archives(limit=1) == ["2026-10"]


def test_unsupported_legacy_archive_is_skipped(tmp_path):
    path = tmp_path / "2021_rr1.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("num.tsv", "x")
        bundle.writestr("txt.tsv", "x")
    assert rr.parse_archive(path)["unsupported"] is True


def test_parse_archive_keeps_fund_rows_and_skips_benchmark_rows(tmp_path):
    archive = make_archive(tmp_path, [
        "A-1\tPerfInceptionDate\tv\t20241231\t14\tS000000001\tC000000001\t\tdoc\tx\ten\t2010-06-30\n",
        # benchmark index row: carries a measure, must be ignored
        "A-1\tPerfInceptionDate\tv\t20241231\t14\tS000000001\tC000000001\tIndex\tdoc\tx\ten\t1990-01-01\n",
        # newer filing for the same class wins
        "A-2\tAnnualReturnInceptionDate\tv\t20241231\t14\tS000000001\tC000000001\t\tdoc\tx\ten\t2010-06-30\n",
        # impossible dates and malformed classes are rejected
        "A-2\tPerfInceptionDate\tv\t20241231\t14\tS000000002\tC000000002\t\tdoc\tx\ten\t1800-01-01\n",
        "A-2\tPerfInceptionDate\tv\t20241231\t14\tS000000003\tBAD\t\tdoc\tx\ten\t2012-01-01\n",
        "A-2\tPerfInceptionDate\tv\t20241231\t14\tS000000004\tC000000004\t\tdoc\tx\ten\t2999-01-01\n",
    ], [
        "A-1\tS000000001\tName\tC000000001\tClass\tabcdx\n",
        "A-1\tS000000001\tName\tC000000005\tClass\t not a ticker!\n",
    ])
    parsed = rr.parse_archive(archive)
    assert list(parsed["inception"]) == ["C000000001"]
    assert parsed["inception"]["C000000001"][1] == date(2010, 6, 30)
    assert parsed["inception"]["C000000001"][2] == "A-2"
    assert parsed["tickers"]["C000000001"][1] == "ABCDX"
    assert "C000000005" not in parsed["tickers"]


def test_collect_counts_conflicts_and_prefers_newest(tmp_path, monkeypatch):
    first = make_archive(tmp_path, [
        "A-1\tPerfInceptionDate\tv\t20241231\t14\tS1\tC000000001\t\tdoc\tx\ten\t2010-06-30\n"], [])
    other = tmp_path / "other"
    other.mkdir()
    second = make_archive(other, [
        "A-2\tPerfInceptionDate\tv\t20241231\t14\tS1\tC000000001\t\tdoc\tx\ten\t2011-01-01\n"], [])
    archives = {"2025q4": second, "2025q3": first}
    monkeypatch.setattr(rr, "download_quarter", lambda quarter, refresh=False: archives.get(quarter))
    data = rr.collect(["2025q4", "2025q3", "2025q2"])
    assert data["quarters_used"] == ["2025q4", "2025q3"]
    assert data["inception"]["C000000001"][1] == date(2011, 1, 1)
    assert data["inception_conflicts"] == 1


def _num(adsh, tag, ddate, series, class_id, value, otherdims=""):
    return (f"{adsh}\t{tag}\tv\t{ddate}\t0\tpure\t{series}\t{class_id}\t\tdoc\t"
            f"{otherdims}\t\t{value}\t\t\t0\t4\n")


def test_parse_archive_imports_fee_bar_chart_and_yield_facts(tmp_path):
    archive = make_archive(tmp_path, [], [], [
        _num("A-1", "MaximumSalesChargeImposedOnPurchasesOverOfferingPrice",
             "20241231", "S000000001", "C000000001", "0.0575"),
        _num("A-1", "ExpenseBreakpointMinimumInvestmentRequiredAmount",
             "20241231", "S000000001", "", "100000"),
        _num("A-1", "BarChartHighestQuarterlyReturn",
             "20241231", "S000000001", "C000000001", "0.2417"),
        _num("A-1", "BarChartHighestQuarterlyReturn",
             "20241231", "S000000001", "", "0.1800"),
        _num("A-1", "MoneyMarketSevenDayYield",
             "20241231", "S000000001", "C000000001", "0.0319"),
        # two unattributable values at the same class/date/document
        _num("A-1", "FeeWaiverOrReimbursementOverAssets",
             "20241231", "S000000001", "C000000001", "-0.0010"),
        _num("A-1", "FeeWaiverOrReimbursementOverAssets",
             "20241231", "S000000001", "C000000001", "-0.0015"),
    ])
    parsed = rr.parse_archive(archive)
    sales = parsed["fees"][("class", "C000000001")]["maximum_sales_charge_purchases"]
    assert sales["value"] == Decimal("0.0575")
    assert sales["unit"] == "fraction"
    minimum = parsed["fees"][("series", "S000000001")]["expense_breakpoint_minimum_investment"]
    assert minimum["value"] == Decimal("100000")
    assert minimum["unit"] == "USD"
    assert parsed["charts"][("class", "C000000001")]["highest_quarterly_return"]["value"] == Decimal("0.2417")
    assert ("series", "S000000001") not in parsed["charts"]
    assert parsed["yields"][("class", "C000000001")]["money_market_seven_day_yield"]["value"] == Decimal("0.0319")
    assert parsed["fees"][("class", "C000000001")]["fee_waiver_or_reimbursement"]["ambiguous"] is True
