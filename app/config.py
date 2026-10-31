from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError(
            "DATABASE_URL is required. Copy .env.example to .env for local development "
            "or configure the intended PostgreSQL URL in the deployment environment."
        )
    if not value.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


def timeout_seconds() -> float:
    return float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))


def user_agent() -> str:
    return os.getenv("USER_AGENT", "GlobalMutualFundETL/0.1")
