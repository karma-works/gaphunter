from __future__ import annotations

import html
import re

import httpx

from app.models import SearchResult
from app.settings import settings


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


def brave_search(query: str, *, limit: int = 5) -> list[SearchResult]:
    if not settings.brave_search_api_key:
        raise SearchError("BRAVE_SEARCH_API_KEY is not configured")

    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": settings.brave_search_api_key,
        },
        params={
            "q": query,
            "count": max(1, min(limit, 20)),
            "country": settings.brave_search_country,
            "search_lang": settings.brave_search_lang,
            "safesearch": "moderate",
            "result_filter": "web",
            "extra_snippets": "true",
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise SearchError(f"Brave Search API returned HTTP {response.status_code}")

    payload = response.json()
    results: list[SearchResult] = []
    for item in payload.get("web", {}).get("results", []):
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue
        snippets = [item.get("description", "")]
        snippets.extend(item.get("extra_snippets") or [])
        snippet = clean_search_text(" ".join(snippet for snippet in snippets if snippet))
        results.append(
            SearchResult(
                title=clean_search_text(title),
                snippet=snippet,
                url=url,
            )
        )
    return results


def custom_search(query: str, search_engine_id: str, *, limit: int = 5) -> list[SearchResult]:
    if not settings.custom_search_api_key:
        raise SearchError("GOOGLE_CUSTOM_SEARCH_API_KEY is not configured")

    response = httpx.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": settings.custom_search_api_key,
            "cx": search_engine_id,
            "q": query,
            "num": max(1, min(limit, 10)),
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise SearchError(f"Custom Search API returned HTTP {response.status_code}")

    payload = response.json()
    results: list[SearchResult] = []
    for item in payload.get("items", []):
        link = item.get("link")
        title = item.get("title")
        if not link or not title:
            continue
        results.append(
            SearchResult(
                title=clean_search_text(title),
                snippet=clean_search_text(item.get("snippet", "")),
                url=link,
            )
        )
    return results


def job_search(query: str, *, limit: int = 5) -> list[SearchResult]:
    if settings.search_provider == "brave":
        return brave_search(query, limit=limit)
    if settings.search_provider != "custom_search":
        raise SearchError(f"Search provider {settings.search_provider!r} is not configured for live search")
    if not settings.job_search_engine_id:
        raise SearchError("JOB_SEARCH_ENGINE_ID is not configured")
    return custom_search(query, settings.job_search_engine_id, limit=limit)


def competitor_search(query: str, *, limit: int = 5) -> list[SearchResult]:
    if settings.search_provider == "brave":
        return brave_search(query, limit=limit)
    if settings.search_provider != "custom_search":
        raise SearchError(f"Search provider {settings.search_provider!r} is not configured for live search")
    if not settings.competitor_search_engine_id:
        raise SearchError("COMPETITOR_SEARCH_ENGINE_ID is not configured")
    return custom_search(query, settings.competitor_search_engine_id, limit=limit)


def search_provider_label() -> str:
    if settings.search_provider == "brave":
        return "Brave Search"
    if settings.search_provider == "custom_search":
        return "Google Custom Search"
    return settings.search_provider
