"""Import official SEC Form N-CEN quarterly bulk data for US funds.

Form N-CEN is the annual census filing for registered investment companies. The
SEC DERA bulk archive carries one row per series plus separate service-provider
tables. Unlike N-PORT (quarterly portfolio) or N-MFP (money-market monthly), it
is the official source for:

* net asset value and market price per share at the end of the reporting period;
* advisory fee and net operating expenses as a percentage of net assets;
* average net assets during the reporting period;
* index-tracking difference and standard deviation for index funds;
* the investment adviser (and adviser start date) and administrator;
* custodian, transfer agent, pricing service, public accountant and underwriter;
* reported fund classification flags (ETF, index, money market, target date, ...).

Every value keeps the filing accession, report-ending period and DERA archive as
provenance. Fund fields are filled only when empty; snapshot datasets are keyed
per source/report date so re-running a quarter is idempotent.
"""
from __future__ import annotations

import csv
import re
import urllib.error
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.holdings.sec_nport import _request
from app.models.schema import Fund, FundProfileSnapshot, NavObservation, Source

SOURCE_ID = "sec_ncen_bulk"
DATASET_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/united_states/ncen_bulk"

ZIP_LINK = re.compile(r'href="(/files/dera/data/form-n-cen-data-sets/[^"]+_ncen(?:_\d+)?\.zip)"')

CLASSIFICATION_FLAGS = {
    "IS_ETF": "exchange_traded_fund",
    "IS_ETMF": "exchange_traded_managed_fund",
    "IS_INDEX": "index_fund",
    "IS_MULTI_INVERSE_INDEX": "multi_inverse_index",
    "IS_INTERVAL": "interval_fund",
    "IS_FUND_OF_FUND": "fund_of_funds",
    "IS_MASTER_FEEDER": "master_feeder",
    "IS_MONEY_MARKET": "money_market",
    "IS_TARGET_DATE": "target_date",
    "IS_UNDERLYING_FUND": "underlying_fund",
    "IS_INDEX_AFFILIATED": "index_affiliated",
    "IS_INDEX_EXCLUSIVE": "index_exclusive",
    "IS_NON_DIVERSIFIED": "non_diversified",
    "IS_SEC_LENDING_AUTHORIZED": "securities_lending_authorized",
}


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned.upper() in {"N/A", "NA", "-", "--"}:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sec_date(value: Any):
    text = _clean(value)
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:11].strip(), fmt).date()
        except ValueError:
            continue
    return None


def _flag(value: Any) -> bool | None:
    text = (_clean(value) or "").upper()
    if text in {"Y", "TRUE", "1"}:
        return True
    if text in {"N", "FALSE", "0"}:
        return False
    return None


def discover_archives(limit: int = 8) -> list[str]:
    """Return the newest N-CEN quarterly bulk archives listed by the SEC."""
    page = _request(DATASET_PAGE).decode("utf-8", errors="replace")
    urls: list[str] = []
    for match in ZIP_LINK.finditer(page):
        url = "https://www.sec.gov" + match.group(1)
        if url not in urls:
            urls.append(url)
    if limit is not None:
        urls = urls[:max(1, limit)]
    return urls


def download_archive(url: str, *, refresh: bool = False) -> tuple[Path, Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    archive = RAW / url.rsplit("/", 1)[-1]
    extract_dir = RAW / archive.stem
    if refresh or not archive.exists():
        partial = archive.with_suffix(archive.suffix + ".part")
        partial.write_bytes(_request(url))
        if not zipfile.is_zipfile(partial):
            partial.unlink(missing_ok=True)
            raise ValueError(f"Download from {url} is not a valid zip archive")
        partial.replace(archive)
    if refresh or not extract_dir.exists():
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extract_dir)
    return archive, extract_dir


def _rows(path: Path) -> Iterator[dict[str, str]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def _submissions(extract_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(extract_dir / "SUBMISSION.tsv"):
        accession = _clean(row.get("ACCESSION_NUMBER"))
        if not accession:
            continue
        result[accession] = {
            "accession": accession,
            "cik": (_clean(row.get("CIK")) or "").zfill(10),
            "filing_date": _sec_date(row.get("FILING_DATE")),
            "report_date": _sec_date(row.get("REPORT_ENDING_PERIOD")),
        }
    return result


def _row_key(row: dict[str, str]) -> str | None:
    """Side tables are keyed by FUND_ID or, for some, by ACCESSION_NUMBER."""
    return _clean(row.get("FUND_ID")) or _clean(row.get("ACCESSION_NUMBER"))


def _first_names(extract_dir: Path, filename: str, column: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in _rows(extract_dir / filename):
        key = _row_key(row)
        name = _clean(row.get(column))
        if key and name and key not in result:
            result[key] = name
    return result


def _advisers(extract_dir: Path) -> dict[str, dict[str, Any]]:
    """Primary adviser per filing; sub-advisers and terminated roles are skipped."""
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(extract_dir / "ADVISER.tsv"):
        key = _row_key(row)
        role = (_clean(row.get("ADVISER_TYPE")) or "").lower()
        name = _clean(row.get("ADVISER_NAME"))
        if not key or not name or key in result:
            continue
        if "sub" in role or "terminated" in role:
            continue
        result[key] = {
            "name": name,
            "start_date": _sec_date(row.get("ADVISOR_START_DATE")),
            "file_number": _clean(row.get("FILE_NUM")),
            "crd_number": _clean(row.get("CRD_NUM")),
            "lei": _clean(row.get("ADVISER_LEI")),
        }
    return result


def _local_series() -> dict[str, list[int]]:
    with SessionLocal() as session:
        rows = session.execute(select(Fund.id, Fund.sec_series_id).where(
            Fund.domicile_country == "US", Fund.sec_series_id.is_not(None))).all()
    grouped: dict[str, list[int]] = defaultdict(list)
    for fund_id, series_id in rows:
        grouped[series_id].append(fund_id)
    return grouped


def _archive_rows(extract_dir: Path, wanted: set[str]) -> list[dict[str, str]]:
    return [row for row in _rows(extract_dir / "FUND_REPORTED_INFO.tsv")
            if _clean(row.get("SERIES_ID")) in wanted]


def _source_url(cik: str, accession: str) -> str:
    if not cik:
        return DATASET_PAGE
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{accession}.txt")


def _ensure_source(session) -> None:
    source = {"source_id": SOURCE_ID, "country_code": "US",
              "organization": "U.S. Securities and Exchange Commission",
              "source_name": "Form N-CEN quarterly bulk data sets",
              "endpoint_url": DATASET_PAGE,
              "verification_status": "Usable Fund Data Confirmed",
              "integration_status": "Integrated", "license_status": "Public domain"}
    session.execute(pg_insert(Source).values(**source).on_conflict_do_update(
        index_elements=[Source.source_id],
        set_={key: value for key, value in source.items() if key != "source_id"}))


def _snapshots(accession: str, row: dict[str, str], *, adviser: dict[str, Any],
               administrator: str | None, custodian: str | None, transfer_agent: str | None,
               pricing_service: str | None, accountant: str | None,
               underwriter: str | None, report_date, source_url: str):
    """Yield (dataset, payload) snapshot candidates derived from one filing row."""
    period = report_date.isoformat() if report_date else None

    management_fee = _decimal(row.get("MANAGEMENT_FEE"))
    net_expenses = _decimal(row.get("NET_OPERATING_EXPENSES"))
    if management_fee is not None:
        yield "expense_ratio_history", {
            "measure": "advisory_fee", "reported_value": str(management_fee),
            "unit": "percent", "effective_date": period,
            "basis": "advisory fee as a percentage of net assets at end of reporting period",
            "accession_number": accession, "source_url": source_url}
    if net_expenses is not None:
        yield "expense_ratio_history", {
            "measure": "net_operating_expenses", "reported_value": str(net_expenses),
            "unit": "percent", "effective_date": period,
            "basis": "net annual operating expenses as a percentage of net assets, net of waivers or reimbursements",
            "accession_number": accession, "source_url": source_url}

    monthly_aum = _decimal(row.get("MONTHLY_AVG_NET_ASSETS"))
    daily_aum = _decimal(row.get("DAILY_AVG_NET_ASSETS"))
    aum, aum_basis = ((monthly_aum, "monthly_average_net_assets")
                      if monthly_aum is not None
                      else (daily_aum, "daily_average_net_assets") if daily_aum is not None
                      else (None, None))
    if aum is not None:
        yield "aum_history", {
            "net_assets": str(aum), "amount": str(aum), "basis": aum_basis,
            "effective_date": period, "accession_number": accession,
            "source_url": source_url}

    nav_per_share = _decimal(row.get("NAV_PER_SHARE"))
    market_price = _decimal(row.get("MARKET_PRICE_PER_SHARE"))
    if nav_per_share is not None or market_price is not None:
        yield "nav_snapshot", {
            "nav_per_share": str(nav_per_share) if nav_per_share is not None else None,
            "market_price_per_share": str(market_price) if market_price is not None else None,
            "effective_date": period, "accession_number": accession,
            "source_url": source_url,
            "scope": "series-level filing; may not identify a single share class"}

    tracking_return = _decimal(row.get("RETURN_AFTR_FEES_AND_EXPENSES"))
    tracking_std = _decimal(row.get("STDV_AFTR_FEES_AND_EXPENSES"))
    if tracking_return is not None or tracking_std is not None:
        yield "performance", {
            "metric": "index_tracking_difference_after_fees",
            "value": str(tracking_return) if tracking_return is not None else None,
            "unit": "percent", "period": "reporting_period",
            "basis": "annualized difference between the fund total return and the index return after fees, as reported by the fund",
            "effective_date": period, "accession_number": accession, "source_url": source_url}
        yield "risk", {
            "volatility_measures": [{
                "period": "reporting_period",
                "std": str(tracking_std) if tracking_std is not None else None,
                "basis": "annualized standard deviation of the daily fund-versus-index return difference after fees",
                "effective_date": period}],
            "accession_number": accession, "source_url": source_url}

    classification = {label: _flag(row.get(column)) for column, label in CLASSIFICATION_FLAGS.items()}
    classification = {key: value for key, value in classification.items() if value is not None}
    if classification:
        yield "classification", {**classification, "effective_date": period,
                                 "accession_number": accession, "source_url": source_url}

    providers = {
        "adviser": ({**adviser, "start_date": adviser["start_date"].isoformat()
                     if adviser and adviser.get("start_date") else None}
                    if adviser else None),
        "administrator": administrator,
        "custodian": custodian, "transfer_agent": transfer_agent,
        "pricing_service": pricing_service, "public_accountant": accountant,
        "principal_underwriter": underwriter,
    }
    if any(providers.values()):
        yield "service_providers", {**providers, "effective_date": period,
                                    "accession_number": accession, "source_url": source_url}


def sync_sec_ncen_bulk(*, quarters: int = 8, refresh: bool = False,
                       update_profiles: bool = True, write_nav: bool = True) -> dict[str, Any]:
    """Import N-CEN profile, fee, performance, classification and NAV snapshots."""
    if quarters < 1:
        raise ValueError("quarters must be at least 1")
    urls = discover_archives(limit=quarters)
    local = _local_series()
    result: dict[str, Any] = {
        "source_id": SOURCE_ID, "archives": urls, "series_targeted": len(local),
        "filings_matched": 0, "series_matched": 0, "snapshot_rows": 0,
        "nav_rows": 0, "profiles_updated": 0, "errors": [],
    }
    if not local:
        return result

    chosen: dict[str, dict[str, Any]] = {}
    for url in urls:
        try:
            _, extract_dir = download_archive(url, refresh=refresh)
            submissions = _submissions(extract_dir)
            rows = _archive_rows(extract_dir, set(local))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
                zipfile.BadZipFile) as error:
            result["errors"].append({"archive": url, "error": f"{type(error).__name__}: {error}"})
            continue
        for row in rows:
            accession = _clean(row.get("ACCESSION_NUMBER"))
            series_id = _clean(row.get("SERIES_ID"))
            submission = submissions.get(accession or "")
            if not accession or not series_id or not submission or not submission["report_date"]:
                continue
            current = chosen.get(series_id)
            if current is None or submission["report_date"] > current["submission"]["report_date"]:
                chosen[series_id] = {"row": row, "submission": submission,
                                     "archive": url, "extract_dir": extract_dir}

    result["series_matched"] = len(chosen)
    result["filings_matched"] = len({entry["submission"]["accession"] for entry in chosen.values()})
    if not chosen:
        return result

    by_archive: dict[Path, list[dict[str, Any]]] = defaultdict(list)
    for entry in chosen.values():
        by_archive[entry["extract_dir"]].append(entry)

    snapshot_values: dict[tuple[int, str], dict[str, Any]] = {}
    nav_values: list[dict[str, Any]] = []
    fund_updates: dict[int, dict[str, Any]] = {}
    for extract_dir, entries in by_archive.items():
        advisers = _advisers(extract_dir)
        administrators = _first_names(extract_dir, "ADMIN.tsv", "ADMIN_NAME")
        custodians = _first_names(extract_dir, "CUSTODIAN.tsv", "CUSTODIAN_NAME")
        transfer_agents = _first_names(extract_dir, "TRANSFER_AGENT.tsv", "TRANSFERAGENT_NAME")
        pricing_services = _first_names(extract_dir, "PRICING_SERVICE.tsv", "PRICING_SERVICE_NAME")
        accountants = _first_names(extract_dir, "PUBLIC_ACCOUNTANT.tsv", "PUB_ACCOUNTANT_NAME")
        underwriters = _first_names(extract_dir, "PRINCIPAL_UNDERWRITER.tsv", "UNDERWRITER_NAME")
        for entry in entries:
            row = entry["row"]
            submission = entry["submission"]
            accession = submission["accession"]
            filing_key = _clean(row.get("FUND_ID")) or accession
            series_id = _clean(row.get("SERIES_ID")) or ""
            report_date = submission["report_date"]
            adviser = advisers.get(filing_key) or advisers.get(accession) or {}
            administrator = administrators.get(filing_key) or administrators.get(accession)
            source_url = _source_url(submission["cik"], accession)
            payloads = list(_snapshots(
                accession, row, adviser=adviser, administrator=administrator,
                custodian=custodians.get(filing_key) or custodians.get(accession),
                transfer_agent=transfer_agents.get(filing_key) or transfer_agents.get(accession),
                pricing_service=pricing_services.get(filing_key) or pricing_services.get(accession),
                accountant=accountants.get(accession), underwriter=underwriters.get(accession),
                report_date=report_date, source_url=source_url))

            fund_ids = local[series_id]
            for fund_id in fund_ids:
                for dataset, payload in payloads:
                    snapshot_key = f"{series_id}:{report_date.isoformat()}:{dataset}:{payload.get('measure') or payload.get('metric') or 'profile'}"
                    snapshot_values[(fund_id, snapshot_key)] = {
                        "fund_id": fund_id, "source_id": SOURCE_ID, "dataset": dataset,
                        "source_report_date": report_date, "snapshot_key": snapshot_key[:64],
                        "payload": payload, "source_url": source_url,
                    }
                if update_profiles:
                    updates = fund_updates.setdefault(fund_id, {})
                    if adviser.get("name") and "manager" not in updates:
                        updates["manager"] = adviser["name"][:300]
                    if administrator and "administrator" not in updates:
                        updates["administrator"] = administrator[:300]
                    if row.get("DAILY_AVG_NET_ASSETS") or row.get("MONTHLY_AVG_NET_ASSETS"):
                        aum = _decimal(row.get("MONTHLY_AVG_NET_ASSETS") or row.get("DAILY_AVG_NET_ASSETS"))
                        if aum is not None:
                            updates.setdefault("net_assets", aum)
                            updates.setdefault("net_assets_date", report_date)

            nav_per_share = _decimal(row.get("NAV_PER_SHARE"))
            # NAV per share is filed at series level. Only attach it when the
            # series maps to exactly one local share class; otherwise the value
            # stays in the series-level snapshot.
            if write_nav and nav_per_share is not None and len(fund_ids) == 1:
                nav_values.append({
                    "fund_id": fund_ids[0], "valuation_date": report_date,
                    "nav": nav_per_share, "currency": "USD", "source_id": SOURCE_ID,
                    "source_url": source_url, "ohlc_basis": "single_daily_nav"})

    with SessionLocal() as session:
        _ensure_source(session)
        snapshot_table = FundProfileSnapshot.__table__
        snapshots = list(snapshot_values.values())
        for offset in range(0, len(snapshots), 400):
            chunk = snapshots[offset:offset + 400]
            statement = pg_insert(snapshot_table).values(chunk)
            session.execute(statement.on_conflict_do_update(
                constraint="uq_fund_profile_source_snapshot",
                set_={"dataset": statement.excluded.dataset,
                      "source_report_date": statement.excluded.source_report_date,
                      "payload": statement.excluded.payload,
                      "source_url": statement.excluded.source_url,
                      "retrieved_at": datetime.now().astimezone()}))
        result["snapshot_rows"] = len(snapshots)

        for offset in range(0, len(nav_values), 400):
            chunk = nav_values[offset:offset + 400]
            statement = pg_insert(NavObservation.__table__).values(chunk)
            # Never replace an existing observation for the same date/currency
            # from an issuer or regulator daily feed with an annual snapshot.
            session.execute(statement.on_conflict_do_nothing(
                constraint="uq_nav_fund_date_currency"))
        result["nav_rows"] = len(nav_values)

        for fund_id, updates in fund_updates.items():
            fund = session.get(Fund, fund_id)
            if fund is None:
                continue
            applied: dict[str, Any] = {}
            if not (fund.manager or "").strip() and updates.get("manager"):
                applied["manager"] = updates["manager"]
            if not (fund.administrator or "").strip() and updates.get("administrator"):
                applied["administrator"] = updates["administrator"]
            if fund.net_assets is None and updates.get("net_assets") is not None:
                applied["net_assets"] = updates["net_assets"]
                applied["net_assets_date"] = updates.get("net_assets_date")
            if applied:
                session.execute(update(Fund).where(Fund.id == fund_id).values(**applied))
                result["profiles_updated"] += 1
        session.commit()
    return result
