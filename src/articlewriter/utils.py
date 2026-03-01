"""
Shared utilities: rate limiting, safe parsing, and escaping for outputs.
"""

import time
from typing import Any


def rate_limit(rpm: int) -> None:
    """Sleep to respect requests-per-minute limit. No-op if rpm <= 0."""
    if rpm <= 0:
        return
    time.sleep(60.0 / rpm)


def safe_year_from_crossref(item: dict[str, Any]) -> int | None:
    """Extract publication year from CrossRef item without raising."""
    for key in ("published-print", "published-online", "created"):
        val = item.get(key)
        if not val or not isinstance(val, dict):
            continue
        parts = val.get("date-parts")
        if not parts or not isinstance(parts, list):
            continue
        first = parts[0]
        if not first or not isinstance(first, (list, tuple)):
            continue
        try:
            y = int(first[0])
            if 1900 <= y <= 2100:
                return y
        except (IndexError, TypeError, ValueError):
            continue
    return None


def bib_escape(s: str) -> str:
    """Escape string for BibTeX note/value: braces and backslashes."""
    if not s:
        return s
    return s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def xml_escape(s: str) -> str:
    """Escape for XML/HTML (e.g. reportlab Paragraph): & < >."""
    if not s:
        return s
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def strip_json_code_fence(raw: str) -> str:
    """Remove markdown code fence (```json ... ```) from LLM output."""
    s = raw.strip()
    if s.startswith("```"):
        lines = s.split("\n", 1)
        s = lines[-1] if len(lines) > 1 else ""
        if s.rstrip().endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()


def get_with_retries(
    url: str,
    *,
    max_retries: int = 3,
    timeout: int = 30,
    **kwargs: Any,
) -> "requests.Response":
    """GET with exponential backoff on 5xx and connection errors."""
    import requests
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=timeout, **kwargs)
            if r.status_code < 500 or attempt == max_retries - 1:
                return r
            last_err = requests.HTTPError(f"HTTP {r.status_code}")
        except (requests.RequestException, OSError) as e:
            last_err = e
        if attempt < max_retries - 1:
            time.sleep(2**attempt)
    raise last_err  # type: ignore[misc]
