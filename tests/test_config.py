import os

from app.config import _normalize_postgres_driver, database_url


def test_normalize_postgres_urls_to_psycopg_driver():
    assert _normalize_postgres_driver("postgresql://db.example.com:5432/mfetl") == "postgresql+psycopg://db.example.com:5432/mfetl"
    assert _normalize_postgres_driver("postgres://db.example.com:5432/mfetl") == "postgresql+psycopg://db.example.com:5432/mfetl"


def test_database_url_preserves_explicit_sqlalchemy_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://db.example.com/mfetl")
    assert database_url() == "postgresql+psycopg://db.example.com/mfetl"


def test_database_url_normalizes_postgresql_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://db.example.com/mfetl")
    assert database_url() == "postgresql+psycopg://db.example.com/mfetl"
