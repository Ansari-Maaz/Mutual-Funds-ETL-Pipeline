from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Source(Base):
    __tablename__ = "sources"
    source_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    organization: Mapped[str] = mapped_column(String(200))
    source_name: Mapped[str] = mapped_column(String(200))
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(40), default="Undiscovered")
    integration_status: Mapped[str] = mapped_column(String(20), default="Not Started")
    license_status: Mapped[str] = mapped_column(String(30), default="Unknown")

class Fund(Base):
    __tablename__ = "funds"
    __table_args__ = (UniqueConstraint("source_id", "source_fund_id", name="uq_fund_source_native"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"), index=True)
    source_fund_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(500))
    domicile_country: Mapped[str | None] = mapped_column(String(2), index=True)
    currency: Mapped[str | None] = mapped_column(String(3))
    isin: Mapped[str | None] = mapped_column(String(12), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(500))
    provider: Mapped[str | None] = mapped_column(String(300), index=True)
    category: Mapped[str | None] = mapped_column(String(200), index=True)
    fund_type: Mapped[str | None] = mapped_column(String(100))
    inception_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(30), index=True)
    official_url: Mapped[str | None] = mapped_column(Text)
    ticker: Mapped[str | None] = mapped_column(String(30), index=True)
    manager: Mapped[str | None] = mapped_column(String(300))
    administrator: Mapped[str | None] = mapped_column(String(300))
    net_assets: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    net_assets_date: Mapped[date | None] = mapped_column(Date)
    target_audience: Mapped[str | None] = mapped_column(String(200))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sec_series_id: Mapped[str | None] = mapped_column(String(10))
    sec_cik: Mapped[str | None] = mapped_column(String(10))
    holdings_status: Mapped[str] = mapped_column(String(20), default="not_checked", server_default="not_checked")
    holdings_report_date: Mapped[date | None] = mapped_column(Date)

class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (UniqueConstraint("fund_id", "reporting_date", "holding_index", name="uq_fund_holding_report_item"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id", ondelete="CASCADE"), index=True)
    reporting_date: Mapped[date] = mapped_column(Date, index=True)
    accession_number: Mapped[str | None] = mapped_column(String(50))
    holding_index: Mapped[int] = mapped_column()
    security_name: Mapped[str | None] = mapped_column(String(500))
    ticker: Mapped[str | None] = mapped_column(String(50))
    isin: Mapped[str | None] = mapped_column(String(12))
    cusip: Mapped[str | None] = mapped_column(String(12))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(36, 12))
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(36, 12))
    market_value_currency: Mapped[str | None] = mapped_column(String(3))
    portfolio_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))
    data_source: Mapped[str] = mapped_column(String(100), default="sec_edgar_nport")
    source_url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class HoldingMetric(Base):
    """Optional vendor/derived metrics; kept separate from filed portfolio positions."""
    __tablename__ = "holding_metrics"
    __table_args__ = (UniqueConstraint("holding_id", "data_source", "as_of_date", name="uq_holding_metric_source_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    holding_id: Mapped[int] = mapped_column(ForeignKey("portfolio_holdings.id", ondelete="CASCADE"), index=True)
    data_source: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    first_bought_date: Mapped[date | None] = mapped_column(Date)
    portfolio_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))
    share_change_percentage: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))
    one_year_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))
    forward_pe: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    sector: Mapped[str | None] = mapped_column(String(200))
    calculation_basis: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class NavObservation(Base):
    __tablename__ = "nav_observations"
    __table_args__ = (UniqueConstraint("fund_id", "valuation_date", "currency", name="uq_nav_fund_date_currency"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id", ondelete="CASCADE"), index=True)
    valuation_date: Mapped[date] = mapped_column(Date, index=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(24, 10))
    currency: Mapped[str] = mapped_column(String(3))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class EtlRun(Base):
    __tablename__ = "etl_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="In Progress")
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.source_id"))
    records_extracted: Mapped[int] = mapped_column(default=0)
    records_loaded: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
