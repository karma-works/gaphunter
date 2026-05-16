from __future__ import annotations

import html
import re

import httpx


class SearchError(RuntimeError):
    pass


_TAG_RE = re.compile(r"<[^>]+>")


def clean_search_text(value: str | None) -> str:
    if not value:
        return ""
    previous = str(value)
    for _ in range(3):
        decoded = html.unescape(previous)
        if decoded == previous:
            break
        previous = decoded
    without_tags = _TAG_RE.sub("", previous).replace("\u2026", "...")
    normalized = re.sub(r"\s+", " ", without_tags).strip()
    return re.sub(r"\.{4,}", "...", normalized)


def brave_search(
    query: str,
    api_key: str,
    *,
    limit: int = 5,
    country: str = "US",
    lang: str = "en",
) -> list[dict]:
    """Calls Brave Search. Returns only results that have both a URL and a title."""
    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
        params={
            "q": query,
            "count": max(1, min(limit, 20)),
            "country": country,
            "search_lang": lang,
            "safesearch": "moderate",
            "result_filter": "web",
            "extra_snippets": "true",
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise SearchError(f"Brave Search API returned HTTP {response.status_code}")

    results = []
    for item in response.json().get("web", {}).get("results", []):
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue
        snippets = [item.get("description", "")]
        snippets.extend(item.get("extra_snippets") or [])
        snippet = clean_search_text(" ".join(s for s in snippets if s))
        results.append({
            "title": clean_search_text(title),
            "url": str(url),
            "snippet": snippet,
            "query": query,
        })
    return results
