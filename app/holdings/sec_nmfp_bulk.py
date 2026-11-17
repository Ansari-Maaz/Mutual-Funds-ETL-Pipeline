"""Import official SEC Form N-MFP monthly bulk data for money-market funds.

The SEC publishes a monthly flat-file data set extracted from N-MFP / N-MFP3
XML filings. Unlike the per-filing import, the bulk archive contains the
schedule of portfolio securities, the series-level adviser/administrator
records, and the class-level daily NAV series in one download.

Money-market funds report under Form N-MFP instead of Form N-PORT, so this is
the official holdings source for that fund type. The SEC daily class NAV table
does not carry a currency field; USD observations are written only when the
caller explicitly opts in with ``assign_usd_nav``, because every selected fund
is U.S. domiciled.
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
from typing import Any, Iterable, Iterator

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.holdings.sec_nport import _request
from app.models.schema import Fund, NavObservation, PortfolioHolding, Source

SOURCE_ID = "sec_nmfp_money_market"
DATASET_PAGE = "https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/united_states/nmfp_bulk"

ZIP_LINK = re.compile(r'href="(/files/dera/data/form-n-mfp-data-sets/[^"]+_nmfp\.zip)"')


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
            return datetime.strptime(text[:11], fmt).date()
        except ValueError:
            continue
    return None


def discover_archives(limit: int = 1) -> list[str]:
    """Return the newest N-MFP monthly bulk archives listed by the SEC."""
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
        payload = _request(url)
        partial = archive.with_suffix(archive.suffix + ".part")
        partial.write_bytes(payload)
        if not zipfile.is_zipfile(partial):
            partial.unlink(missing_ok=True)
            raise ValueError(f"Download from {url} is not a valid zip archive")
        partial.replace(archive)
    if refresh or not extract_dir.exists():
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extract_dir)
    return archive, extract_dir


def _rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def _submissions(extract_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(extract_dir / "NMFP_SUBMISSION.tsv"):
        accession = _clean(row.get("ACCESSION_NUMBER"))
        series_id = _clean(row.get("SERIESID"))
        if not accession or not series_id:
            continue
        result[accession] = {
            "accession": accession,
            "series_id": series_id,
            "report_date": _sec_date(row.get("REPORTDATE")),
            "cik": (_clean(row.get("CIK")) or "").zfill(10),
            "registrant": _clean(row.get("REGISTRANTFULLNAME")),
            "series_name": _clean(row.get("NAMEOFSERIES")) or _clean(row.get("SERIES_NAME")),
        }
    return result


def _names(extract_dir: Path, filename: str, column: str) -> dict[str, str]:
    result: dict[str, str] = {}
    path = extract_dir / filename
    if not path.exists():
        return result
    for row in _rows(path):
        accession = _clean(row.get("ACCESSION_NUMBER"))
        name = _clean(row.get(column))
        if accession and name and accession not in result:
            result[accession] = name
    return result


def _local_funds(*, only_missing: bool) -> dict[str, list[int]]:
    with SessionLocal() as session:
        rows = session.execute(select(Fund.id, Fund.sec_series_id).where(
            Fund.domicile_country == "US", Fund.sec_series_id.is_not(None))).all()
        grouped: dict[str, list[int]] = defaultdict(list)
        for fund_id, series_id in rows:
            grouped[series_id].append(fund_id)
        if only_missing:
            covered = set(session.execute(
                select(PortfolioHolding.fund_id).distinct()).scalars().all())
            grouped = {series: [fund_id for fund_id in ids if fund_id not in covered]
                       for series, ids in grouped.items()
                       if any(fund_id not in covered for fund_id in ids)}
        return grouped


def _holdings_rows(extract_dir: Path, accessions: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Read only the requested accessions while streaming the large TSV."""
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    path = extract_dir / "NMFP_SCHPORTFOLIOSECURITIES.tsv"
    if not path.exists():
        return result
    for row in _rows(path):
        accession = _clean(row.get("ACCESSION_NUMBER"))
        if not accession or accession not in accessions:
            continue
        name = _clean(row.get("TITLEOFISSUER")) or _clean(row.get("NAMEOFISSUER"))
        if not name:
            continue
        raw_index = _clean(row.get("SECURITY_ID"))
        try:
            index = int(raw_index) if raw_index else len(result[accession]) + 1
        except ValueError:
            index = len(result[accession]) + 1
        percentage = _decimal(row.get("PERCENTAGEOFMONEYMARKETFUNDNET"))
        cusip = _clean(row.get("CUSIP_NUMBER"))
        isin = _clean(row.get("ISIN"))
        result[accession].append({
            "holding_index": index,
            "security_name": name[:500],
            "cusip": cusip[:12] if cusip and cusip.upper() != "N/A" else None,
            "isin": isin[:12] if isin and isin.upper() != "N/A" else None,
            # The bulk field is a fraction of money-market fund net assets.
            "portfolio_weight": percentage * 100 if percentage is not None else None,
        })
    return result


def _daily_nav_rows(extract_dir: Path, accessions: set[str]) -> dict[str, list[dict[str, Any]]]:
    path = extract_dir / "NMFP_DLYNETASSETVALUEPERSHARC.tsv"
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return result
    for row in _rows(path):
        accession = _clean(row.get("ACCESSION_NUMBER"))
        if not accession or accession not in accessions:
            continue
        class_id = _clean(row.get("CLASSESID"))
        nav = _decimal(row.get("DLYNETASSETVALUEPERSHARECLASS"))
        valuation_date = _sec_date(row.get("DLYNETASSETVALUEPERSHAREDATEC"))
        # SEC bulk rows can explicitly carry zero where no positive class NAV
        # was reported. Zero is not a usable per-share NAV and must not make a
        # fund appear NAV-covered or be returned as a customer price.
        if not class_id or nav is None or nav <= 0 or valuation_date is None:
            continue
        result[accession].append({"class_id": class_id, "valuation_date": valuation_date, "nav": nav})
    return result


def _ensure_source(session) -> None:
    source = {"source_id": SOURCE_ID, "country_code": "US",
              "organization": "U.S. Securities and Exchange Commission",
              "source_name": "Form N-MFP monthly bulk data sets",
              "endpoint_url": DATASET_PAGE,
              "verification_status": "Usable Fund Data Confirmed",
              "integration_status": "Integrated", "license_status": "Public domain"}
    session.execute(pg_insert(Source).values(**source).on_conflict_do_update(
        index_elements=[Source.source_id],
        set_={key: value for key, value in source.items() if key != "source_id"}))


def sync_sec_nmfp_bulk(*, months: int = 1, only_missing: bool = True,
                       assign_usd_nav: bool = False, update_profiles: bool = True,
                       refresh: bool = False) -> dict[str, Any]:
    """Import N-MFP holdings, adviser/administrator and optional USD NAV rows.

    Only the newest report date per series across the downloaded archives is
    imported, so loading several months does not duplicate older snapshots.
    """
    if months < 1:
        raise ValueError("months must be at least 1")
    urls = discover_archives(limit=months)
    local = _local_funds(only_missing=only_missing)
    result: dict[str, Any] = {
        "source_id": SOURCE_ID, "archives": urls, "series_targeted": len(local),
        "filings_matched": 0, "funds_loaded": 0, "holding_rows": 0,
        "nav_rows": 0, "profiles_updated": 0, "errors": [],
    }
    if not local:
        return result

    # Choose the newest filing per series across every downloaded archive.
    chosen: dict[str, dict[str, Any]] = {}
    archive_by_accession: dict[str, Path] = {}
    for url in urls:
        try:
            _, extract_dir = download_archive(url, refresh=refresh)
            submissions = _submissions(extract_dir)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, zipfile.BadZipFile) as error:
            result["errors"].append({"archive": url, "error": f"{type(error).__name__}: {error}"})
            continue
        for accession, info in submissions.items():
            if info["series_id"] not in local or info["report_date"] is None:
                continue
            current = chosen.get(info["series_id"])
            if current is None or info["report_date"] > current["report_date"]:
                chosen[info["series_id"]] = info
                archive_by_accession[accession] = extract_dir

    holdings_by_archive: dict[Path, set[str]] = defaultdict(set)
    for info in chosen.values():
        extract_dir = archive_by_accession.get(info["accession"])
        if extract_dir is not None:
            holdings_by_archive[extract_dir].add(info["accession"])

    values: list[dict[str, Any]] = []
    nav_values: list[dict[str, Any]] = []
    profile_updates: list[tuple[int, dict[str, Any]]] = []
    chosen_by_accession = {info["accession"]: info for info in chosen.values()}
    matched_accessions = set(chosen_by_accession)
    result["filings_matched"] = len(matched_accessions)
    funds_by_series = {info["series_id"]: local[info["series_id"]] for info in chosen.values()}
    report_date_by_fund = {
        fund_id: info["report_date"]
        for info in chosen.values() for fund_id in funds_by_series[info["series_id"]]
    }
    targeted_funds = set(report_date_by_fund)

    for extract_dir, accessions in holdings_by_archive.items():
        holdings = _holdings_rows(extract_dir, accessions)
        adviser = _names(extract_dir, "NMFP_ADVISER.tsv", "ADVISERNAME")
        administrator = _names(extract_dir, "NMFP_ADMINISTRATOR.tsv", "ADMINISTRATORNAME")
        nav_rows = _daily_nav_rows(extract_dir, accessions) if assign_usd_nav else {}
        class_to_funds: dict[str, list[int]] = defaultdict(list)
        if assign_usd_nav:
            with SessionLocal() as session:
                for fund_id, class_id in session.execute(select(
                        Fund.id, Fund.source_fund_id).where(
                        Fund.domicile_country == "US", Fund.sec_series_id.is_not(None))).all():
                    class_to_funds[class_id].append(fund_id)
        for accession in accessions:
            info = chosen_by_accession[accession]
            fund_ids = funds_by_series.get(info["series_id"], [])
            report_date = info["report_date"]
            cik = info["cik"] or ""
            source_url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                          f"{accession.replace('-', '')}/{accession}.txt" if cik else DATASET_PAGE)
            for holding in holdings.get(accession, []):
                for fund_id in fund_ids:
                    values.append({
                        "fund_id": fund_id, "reporting_date": report_date,
                        "accession_number": accession,
                        "holding_index": holding["holding_index"],
                        "security_name": holding["security_name"],
                        "cusip": holding["cusip"], "isin": holding["isin"],
                        "portfolio_weight": holding["portfolio_weight"],
                        "source_url": source_url,
                        "data_source": "sec_nmfp_bulk",
                    })
            if assign_usd_nav:
                for row in nav_rows.get(accession, []):
                    for fund_id in class_to_funds.get(row["class_id"], []):
                        nav_values.append({
                            "fund_id": fund_id, "valuation_date": row["valuation_date"],
                            "nav": row["nav"], "currency": "USD", "source_id": SOURCE_ID,
                            "source_url": source_url, "ohlc_basis": "single_daily_nav",
                        })
            if update_profiles:
                metadata: dict[str, Any] = {"category": "Money market"}
                if adviser.get(accession):
                    metadata["manager"] = adviser[accession][:300]
                if administrator.get(accession):
                    metadata["administrator"] = administrator[accession][:300]
                for fund_id in fund_ids:
                    profile_updates.append((fund_id, metadata))

    with SessionLocal() as session:
        _ensure_source(session)
        table = PortfolioHolding.__table__
        for offset in range(0, len(values), 400):
            chunk = values[offset:offset + 400]
            statement = pg_insert(table).values(chunk)
            update_columns = {key: getattr(statement.excluded, key) for key in chunk[0]
                              if key not in {"id", "fund_id", "reporting_date", "holding_index"}}
            session.execute(statement.on_conflict_do_update(
                constraint="uq_fund_holding_report_item", set_=update_columns))
        result["holding_rows"] = len(values)

        for offset in range(0, len(nav_values), 400):
            chunk = nav_values[offset:offset + 400]
            statement = pg_insert(NavObservation.__table__).values(chunk)
            session.execute(statement.on_conflict_do_update(
                constraint="uq_nav_fund_date_currency",
                set_={"nav": statement.excluded.nav, "source_id": statement.excluded.source_id,
                      "source_url": statement.excluded.source_url,
                      "ohlc_basis": statement.excluded.ohlc_basis,
                      "retrieved_at": datetime.now().astimezone()}))
        result["nav_rows"] = len(nav_values)

        # Fill only empty profile fields; never overwrite sourced values.
        profile_by_fund: dict[int, dict[str, Any]] = {}
        for fund_id, metadata in profile_updates:
            profile_by_fund.setdefault(fund_id, metadata)
        for fund_id, metadata in profile_by_fund.items():
            fund = session.get(Fund, fund_id)
            if fund is None:
                continue
            updates: dict[str, Any] = {}
            if not (fund.manager or "").strip() and metadata.get("manager"):
                updates["manager"] = metadata["manager"]
            if not (fund.administrator or "").strip() and metadata.get("administrator"):
                updates["administrator"] = metadata["administrator"]
            if not (fund.category or "").strip():
                updates["category"] = "Money market"
            if updates:
                session.execute(update(Fund).where(Fund.id == fund_id).values(**updates))
                result["profiles_updated"] += 1
        if values:
            for fund_id in targeted_funds:
                session.execute(update(Fund).where(Fund.id == fund_id).values(
                    holdings_status="available",
                    holdings_report_date=report_date_by_fund[fund_id]))
        session.commit()
        result["funds_loaded"] = len(targeted_funds)
    return result
