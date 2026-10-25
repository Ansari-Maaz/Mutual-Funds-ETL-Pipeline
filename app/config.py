from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

def _normalize_postgres_driver(url: str) -> str:
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url

def database_url() -> str:
    raw_url = os.getenv("DATABASE_URL", "******localhost:5433/mfetl")
    return _normalize_postgres_driver(raw_url)

def timeout_seconds() -> float:
    return float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))

def user_agent() -> str:
    return os.getenv("USER_AGENT", "GlobalMutualFundETL/0.1")
