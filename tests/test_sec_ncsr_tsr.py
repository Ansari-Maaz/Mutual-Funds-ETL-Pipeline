from datetime import date

from app.enrichment.sec_ncsr_tsr import _dedupe_returns, _merge_records, parse_tsr_instance

NS = (
    'xmlns:xbrli="http://www.xbrl.org/2003/instance" '
    'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
    'xmlns:oef="http://xbrl.sec.gov/oef/2024" '
    'xmlns:dei="http://xbrl.sec.gov/dei/2024" '
    'xmlns:nacc2="http://xbrl.sec.gov/nacc2/2024"'
)

DOCUMENT_CONTEXT = """
  <xbrli:context id="doc">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000036405</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
"""


def class_context(context_id: str, class_id: str, start: str, end: str, *extra: str) -> str:
    dimensions = "".join(
        f'<xbrldi:explicitMember dimension="{dimension}">{member}</xbrldi:explicitMember>'
        for dimension, member in extra
    )
    return f"""
  <xbrli:context id="{context_id}">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000036405</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="oef:ClassAxis">nacc2:{class_id}Member</xbrldi:explicitMember>
        <xbrldi:explicitMember dimension="oef:LegalEntityAxis">nacc2:S000000001Member</xbrldi:explicitMember>
        {dimensions}
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period>
  </xbrli:context>
"""


def build_instance() -> bytes:
    contexts = [
        DOCUMENT_CONTEXT,
        class_context("c1", "C000007773", "2025-01-01", "2025-12-31"),
        class_context("c1n", "C000007773", "2025-01-01", "2025-12-31",
                      ("oef:SalesLoadAxis", "oef:WithoutSalesLoadMember")),
        class_context("c5", "C000007773", "2021-01-01", "2025-12-31"),
        class_context("sec", "C000007773", "2025-12-31", "2025-12-31",
                      ("oef:IndustrySectorAxis", "oef:SectorInformationTechnologySectorMember")),
        class_context("idx", "C000007773", "2025-01-01", "2025-12-31",
                      ("oef:IndexAxis", "oef:SP500IndexMember")),
    ]
    facts = [
        '<dei:DocumentPeriodEndDate contextRef="doc">2025-12-31</dei:DocumentPeriodEndDate>',
        '<dei:DocumentType contextRef="doc">N-CSR</dei:DocumentType>',
        '<oef:TradingSymbol contextRef="c1">vfinx</oef:TradingSymbol>',
        '<oef:ClassName contextRef="c1">Investor Shares</oef:ClassName>',
        '<oef:FundName contextRef="c1">500 Index Fund</oef:FundName>',
        '<oef:ExpenseRatioPct contextRef="c1">0.0014</oef:ExpenseRatioPct>',
        '<oef:AssetsNet contextRef="c1">1480375000000</oef:AssetsNet>',
        '<oef:HoldingsCount contextRef="c1">517</oef:HoldingsCount>',
        '<oef:InvestmentCompanyPortfolioTurnover contextRef="c1">0.02</oef:InvestmentCompanyPortfolioTurnover>',
        '<oef:PerfInceptionDate contextRef="c1">1976-08-31</oef:PerfInceptionDate>',
        '<oef:AvgAnnlRtrPct contextRef="c1">0.1771</oef:AvgAnnlRtrPct>',
        '<oef:AvgAnnlRtrPct contextRef="c1n">0.1771</oef:AvgAnnlRtrPct>',
        '<oef:AvgAnnlRtrPct contextRef="c5">0.1426</oef:AvgAnnlRtrPct>',
        '<oef:AvgAnnlRtrPct contextRef="idx">0.1800</oef:AvgAnnlRtrPct>',
        '<oef:PctOfNav contextRef="sec">0.106</oef:PctOfNav>',
        '<oef:ExpensesPaidAmt contextRef="c1">15</oef:ExpensesPaidAmt>',
    ]
    return (f'<xbrli:xbrl {NS}>' + "".join(contexts) + "".join(facts) + "</xbrli:xbrl>").encode()


def parse():
    parsed = parse_tsr_instance(
        build_instance(), accession="0001104659-26-021519",
        filing_date=date(2026, 3, 1), form="N-CSR",
        source_url="https://www.sec.gov/x", instance_url="https://www.sec.gov/y")
    assert parsed is not None
    return parsed


def test_document_facts_are_kept():
    parsed = parse()
    assert parsed["document"]["DocumentType"] == "N-CSR"
    assert parsed["document"]["DocumentPeriodEndDate"] == "2025-12-31"


def test_class_scalar_facts_are_read():
    record = parse()["classes"]["C000007773"]
    assert record["TradingSymbol"] == "vfinx"
    assert record["ClassName"] == "Investor Shares"
    assert record["ExpenseRatioPct"] == "0.0014"
    assert record["HoldingsCount"] == "517"
    assert record["PerfInceptionDate"] == "1976-08-31"
    assert record["series_id"] == "S000000001"


def test_returns_drop_index_rows_and_prefer_no_load():
    returns = parse()["classes"]["C000007773"]["returns"]
    assert [item["years"] for item in returns] == [1, 5]
    one_year = returns[0]
    assert one_year["average_annual_return_fraction"] == "0.1771"
    assert one_year["load_basis"] == "without_sales_load"
    # The benchmark-index row for the same period must never replace the class return.
    assert all(item["average_annual_return_fraction"] != "0.1800" for item in returns)


def test_sector_weight_is_readable_and_absolute():
    sectors = parse()["classes"]["C000007773"]["sector_allocation"]
    assert len(sectors) == 1
    assert sectors[0]["sector"] == "Information Technology"
    assert sectors[0]["weight_pct"] == "10.600"


def test_expense_examples_carry_period():
    examples = parse()["classes"]["C000007773"]["expense_examples"]
    assert examples[0]["measure"] == "ExpensesPaidAmt"
    assert examples[0]["value"] == "15"
    assert examples[0]["start_date"] == "2025-01-01"


def test_merge_keeps_newest_scalars_and_older_returns():
    old = {
        "report_date": date(2025, 6, 30), "TradingSymbol": "OLD", "ClassName": "Investor",
        "returns": [{"start_date": "2015-01-01", "end_date": "2024-12-31", "years": 10,
                     "average_annual_return_fraction": "0.14",
                     "load_basis": "without_sales_load"}],
        "sector_allocation": [{"sector": "Old"}], "expense_examples": [],
    }
    new = {
        "report_date": date(2026, 6, 30), "TradingSymbol": "NEW", "holdings_count": "500",
        "returns": [{"start_date": "2025-01-01", "end_date": "2025-12-31", "years": 1,
                     "average_annual_return_fraction": "0.17",
                     "load_basis": "without_sales_load"}],
        "sector_allocation": [], "expense_examples": [],
    }
    merged = _merge_records(old, new)
    assert merged["TradingSymbol"] == "NEW"
    assert merged["ClassName"] == "Investor"  # newer filing omitted it, older value survives
    assert merged["report_date"] == date(2026, 6, 30)
    assert {item["years"] for item in merged["returns"]} == {1, 10}
    # A newer filing with an empty sector list must not erase older weights.
    assert merged["sector_allocation"] == old["sector_allocation"]


def test_dedupe_returns_prefers_no_load_and_sorts_by_horizon():
    rows = [
        {"start_date": "2025-01-01", "end_date": "2025-12-31", "years": 1,
         "load_basis": "as_reported"},
        {"start_date": "2025-01-01", "end_date": "2025-12-31", "years": 1,
         "load_basis": "without_sales_load"},
        {"start_date": "2016-01-01", "end_date": "2025-12-31", "years": 10,
         "load_basis": "as_reported"},
    ]
    deduped = _dedupe_returns(rows)
    assert len(deduped) == 2
    assert deduped[0]["load_basis"] == "without_sales_load"
    assert [item["years"] for item in deduped] == [1, 10]
