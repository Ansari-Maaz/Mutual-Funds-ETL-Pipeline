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
