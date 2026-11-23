"""Derive holding analytics from consecutive official N-PORT filings.

No vendor data is used.  Every value in ``holding_metrics`` produced here is a
deterministic function of SEC-filed positions:

* ``first_bought_date`` - the earliest N-PORT report period in the imported
  archive window in which the same security appears for the fund.  For a
  position already held at the start of the window this is a lower bound, not a
  claim about the true purchase date.
* ``share_change_percentage`` - quantity in the current filed period versus the
  fund's immediately preceding filed period, for the same security and unit.
* ``one_year_return`` - change in filed market value per share (or per principal
  unit for debt) between report periods roughly 12 months apart.  This is a
  price change, not total return: distributions are not included and a split is
  not adjusted unless the filer reports the post-split quantity.
* ``sector`` - the issuer's SEC EDGAR SIC group, resolved through the official
  CUSIP -> ticker crosswalk.  SIC is an issuer industry classification, not a
  GICS sector, and the code is recorded in ``calculation_basis``.

``forward_pe`` is intentionally never written: no official U.S. source publishes
a forward earnings estimate for a portfolio holding.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import database_url
from app.db.session import SessionLocal
from app.holdings.sec_nport_identifiers import INDUSTRY_SOURCE
from app.models.schema import Source

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
METRIC_SOURCE = "sec_nport_derived"
MIN_REPORT_DATE = date(2019, 1, 1)  # DERA N-PORT bulk archives start in 2019q4
MAX_SANE_RETURN = 500.0
MIN_SANE_RETURN = -95.0
# share_change_percentage is Numeric(18, 12): anything larger cannot be stored
# and is not a credible filed quantity change.
MAX_SANE_SHARE_CHANGE = 100000.0

BASIS = (
    "Derived only from SEC Form N-PORT filings. First reported: earliest report "
    "period for this fund and security in the imported archive window (a lower "
    "bound when the position was already held at the window start). Share change: "
    "quantity versus the fund's previous N-PORT report, same security and unit. "
    "1Y return: change in filed market value per share/principal between report "
    "dates about 12 months apart; excludes distributions and is not split-adjusted."
)


def _raw_url() -> str:
    return database_url().replace("postgresql+psycopg://", "postgresql://", 1)


def _ensure_source() -> None:
    definition = {
        "source_id": METRIC_SOURCE, "country_code": "US",
        "organization": "FundFlow derived from U.S. Securities and Exchange Commission filings",
        "source_name": "N-PORT-derived holding analytics",
        "endpoint_url": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets",
        "verification_status": "Usable Fund Data Confirmed",
        "integration_status": "Integrated", "license_status": "Public SEC filing",
    }
    with SessionLocal() as session:
        statement = pg_insert(Source).values(**definition)
        session.execute(statement.on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in definition.items() if key != "source_id"}))
        session.commit()


def sync_nport_holding_metrics(*, refresh: bool = False, latest_only: bool = True) -> dict[str, Any]:
    """Compute and upsert derived metrics for imported N-PORT positions.

    The full filing history is aggregated once so prior-period metrics exist,
    but the expensive year-over-year and share-change joins are restricted to
    the reports being written (by default each fund's newest filed report).
    """
    _ensure_source()
    counts: dict[str, Any] = {}
    with psycopg.connect(_raw_url(), autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TEMP TABLE stg_metric_base ON COMMIT DROP AS
                SELECT id, fund_id, reporting_date, quantity, market_value, unit,
                       source_url, upper(btrim(ticker)) AS ticker,
                       COALESCE(
                           NULLIF(upper(btrim(cusip)), ''),
                           NULLIF(upper(btrim(isin)), ''),
                           upper(btrim(security_name))
                       ) AS security_key
                FROM portfolio_holdings
                WHERE data_source IN ('sec_edgar_nport_bulk', 'sec_edgar_nport')
                  AND reporting_date >= %s
            """, (MIN_REPORT_DATE,))
            # Keep the normalized per-holding keys in a temp table so the final
            # join never has to evaluate upper(btrim(...)) on the 85M-row live
            # holdings table again.
            cursor.execute("""
                CREATE TEMP TABLE stg_holding_keys ON COMMIT DROP AS
                SELECT id AS holding_id, fund_id, reporting_date, source_url,
                       ticker, security_key
                FROM stg_metric_base
            """)
            cursor.execute("""
                CREATE TEMP TABLE stg_positions ON COMMIT DROP AS
                SELECT fund_id, reporting_date, security_key,
                       sum(quantity) AS quantity,
                       sum(market_value) AS market_value,
                       CASE WHEN count(DISTINCT unit) = 1 THEN min(unit) END AS unit,
                       max(source_url) AS source_url
                FROM stg_metric_base
                GROUP BY 1, 2, 3
            """)
            cursor.execute("DROP TABLE stg_metric_base")
            cursor.execute("CREATE INDEX ON stg_holding_keys (fund_id, reporting_date, security_key)")
            cursor.execute("ANALYZE stg_holding_keys")
            cursor.execute("CREATE INDEX ON stg_positions (fund_id, reporting_date)")
            cursor.execute("CREATE INDEX ON stg_positions (fund_id, security_key, reporting_date)")
            cursor.execute("ANALYZE stg_positions")

            if latest_only:
                cursor.execute("""
                    CREATE TEMP TABLE stg_output_reports ON COMMIT DROP AS
                    SELECT fund_id, max(reporting_date) AS reporting_date
                    FROM stg_positions GROUP BY 1
                """)
            else:
                cursor.execute("""
                    CREATE TEMP TABLE stg_output_reports ON COMMIT DROP AS
                    SELECT DISTINCT fund_id, reporting_date FROM stg_positions
                """)
            cursor.execute("CREATE INDEX ON stg_output_reports (fund_id, reporting_date)")
            cursor.execute("""
                CREATE TEMP TABLE stg_targets ON COMMIT DROP AS
                SELECT p.fund_id, p.reporting_date, p.security_key, p.quantity,
                       p.market_value, p.unit
                FROM stg_positions p
                JOIN stg_output_reports o USING (fund_id, reporting_date)
            """)
            cursor.execute("ANALYZE stg_targets")

            # Previous filed date for each target, from the full position history.
            cursor.execute("""
                CREATE TEMP TABLE stg_prev_dates ON COMMIT DROP AS
                SELECT o.fund_id, o.reporting_date,
                       (SELECT max(d.reporting_date) FROM stg_positions d
                        WHERE d.fund_id = o.fund_id
                          AND d.reporting_date < o.reporting_date) AS prev_date
                FROM stg_output_reports o
            """)
            cursor.execute("""
                CREATE TEMP TABLE stg_share ON COMMIT DROP AS
                SELECT t.fund_id, t.reporting_date, t.security_key,
                       CASE WHEN prev.quantity IS NOT NULL AND prev.quantity <> 0
                                 AND t.unit IS NOT NULL AND t.unit = prev.unit
                             THEN round((t.quantity - prev.quantity)
                                        / abs(prev.quantity) * 100, 6)
                       END AS share_change_percentage
                FROM stg_targets t
                JOIN stg_prev_dates d USING (fund_id, reporting_date)
                LEFT JOIN stg_positions prev
                  ON prev.fund_id = t.fund_id
                 AND prev.reporting_date = d.prev_date
                 AND prev.security_key = t.security_key
            """)
            cursor.execute("""
                DELETE FROM stg_share
                WHERE share_change_percentage IS NOT NULL
                  AND abs(share_change_percentage) > %s
            """, (MAX_SANE_SHARE_CHANGE,))

            cursor.execute("""
                CREATE TEMP TABLE stg_year ON COMMIT DROP AS
                SELECT DISTINCT ON (t.fund_id, t.reporting_date, t.security_key)
                       t.fund_id, t.reporting_date, t.security_key,
                       CASE WHEN t.quantity <> 0 AND prev.quantity <> 0
                                 AND t.unit IN ('NS', 'PA') AND t.unit = prev.unit
                                 AND t.market_value > 0 AND prev.market_value > 0
                             THEN round((
                                 (t.market_value / t.quantity)
                                 / (prev.market_value / prev.quantity) - 1) * 100, 6)
                       END AS one_year_return
                FROM stg_targets t
                JOIN stg_positions prev
                  ON prev.fund_id = t.fund_id
                 AND prev.security_key = t.security_key
                 AND t.reporting_date - prev.reporting_date BETWEEN 360 AND 370
                ORDER BY t.fund_id, t.reporting_date, t.security_key,
                         abs(t.reporting_date - (prev.reporting_date + 365))
            """)
            cursor.execute("""
                UPDATE stg_year SET one_year_return = NULL
                WHERE one_year_return < %s OR one_year_return > %s
            """, (MIN_SANE_RETURN, MAX_SANE_RETURN))

            cursor.execute("""
                CREATE TEMP TABLE stg_first ON COMMIT DROP AS
                SELECT t.fund_id, t.security_key,
                       min(p.reporting_date) AS first_bought_date
                FROM (SELECT DISTINCT fund_id, security_key FROM stg_targets) t
                JOIN stg_positions p
                  ON p.fund_id = t.fund_id AND p.security_key = t.security_key
                GROUP BY 1, 2
            """)

            # All joins now use temp tables built from the single initial scan;
            # the live 85-million-row holdings table is not touched again.
            cursor.execute("""
                CREATE TEMP TABLE stg_metrics ON COMMIT DROP AS
                SELECT h.holding_id, h.source_url, h.reporting_date,
                       f.first_bought_date, s.share_change_percentage,
                       y.one_year_return, si.sector, si.sic, si.sic_description
                FROM stg_holding_keys h
                JOIN stg_output_reports o
                  ON o.fund_id = h.fund_id AND o.reporting_date = h.reporting_date
                JOIN stg_targets p
                  ON p.fund_id = h.fund_id AND p.reporting_date = h.reporting_date
                 AND p.security_key = h.security_key
                LEFT JOIN stg_first f
                  ON f.fund_id = h.fund_id AND f.security_key = p.security_key
                LEFT JOIN stg_share s
                  ON s.fund_id = p.fund_id AND s.reporting_date = p.reporting_date
                 AND s.security_key = p.security_key
                LEFT JOIN stg_year y
                  ON y.fund_id = p.fund_id AND y.reporting_date = p.reporting_date
                 AND y.security_key = p.security_key
                LEFT JOIN security_industry si
                  ON si.ticker = h.ticker
            """)
            cursor.execute("SELECT count(*) FROM stg_metrics")
            counts["metric_rows_computed"] = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO holding_metrics (
                    holding_id, data_source, source_url, as_of_date,
                    first_bought_date, portfolio_weight, share_change_percentage,
                    one_year_return, forward_pe, sector, calculation_basis, retrieved_at
                )
                SELECT holding_id, %s, source_url, reporting_date,
                       first_bought_date, NULL, share_change_percentage,
                       one_year_return, NULL, sector,
                       %s || CASE WHEN sic IS NOT NULL
                                  THEN ' Sector basis: SEC SIC ' || sic
                                       || COALESCE(' - ' || sic_description, '')
                                  ELSE ' Sector basis: no SIC match for the filed ticker.'
                             END,
                       now()
                FROM stg_metrics
                ON CONFLICT (holding_id, data_source, as_of_date)
                DO UPDATE SET
                    source_url = EXCLUDED.source_url,
                    first_bought_date = EXCLUDED.first_bought_date,
                    share_change_percentage = EXCLUDED.share_change_percentage,
                    one_year_return = EXCLUDED.one_year_return,
                    sector = EXCLUDED.sector,
                    calculation_basis = EXCLUDED.calculation_basis,
                    retrieved_at = EXCLUDED.retrieved_at
            """, (METRIC_SOURCE, BASIS))
            counts["metric_rows_written"] = cursor.rowcount
        connection.commit()

    counts["metric_source"] = METRIC_SOURCE
    counts["industry_source"] = INDUSTRY_SOURCE
    counts["completed_at"] = datetime.now(timezone.utc).isoformat()
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sec_nport_holding_metrics.json").write_text(json.dumps(counts, indent=2) + "\n")
    return counts
