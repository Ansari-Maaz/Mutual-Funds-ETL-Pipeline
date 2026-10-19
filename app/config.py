from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql+psycopg://mfetl:mfetl@localhost:5433/mfetl")

def timeout_seconds() -> float:
    return float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))

def user_agent() -> str:
    return os.getenv("USER_AGENT", "GlobalMutualFundETL/0.1")
