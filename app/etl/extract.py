"""Shared extraction helpers. Provider connectors own parsing and pagination."""
from datetime import datetime, timezone
from typing import Any
import hashlib
import httpx
from app.config import timeout_seconds, user_agent

def fetch_snapshot(url: str) -> dict[str, Any]:
    response = httpx.get(url, timeout=timeout_seconds(), follow_redirects=True,
                         headers={"User-Agent": user_agent(), "Accept": "application/json, text/csv, application/xml;q=0.9, */*;q=0.1"})
    body = response.content
    return {"url": str(response.url), "timestamp": datetime.now(timezone.utc).isoformat(),
      "status": response.status_code, "content_type": response.headers.get("content-type", ""),
      "response_size": len(body), "sha256": hashlib.sha256(body).hexdigest(),
      "preview": body[:500].decode("utf-8", errors="replace"), "body": body}
