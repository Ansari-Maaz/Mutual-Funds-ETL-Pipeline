from __future__ import annotations
from typing import Any
import httpx
from app.config import timeout_seconds, user_agent

def get_json(url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """Make one bounded, identifiable request; callers must respect source terms."""
    return httpx.get(url, params=params, timeout=timeout_seconds(), headers={"User-Agent": user_agent(), "Accept": "application/json"}, follow_redirects=True)
