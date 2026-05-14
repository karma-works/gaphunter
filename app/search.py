from __future__ import annotations

import httpx

from app.models import SearchResult
from app.settings import settings


class SearchError(RuntimeError):
    pass


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
                title=title,
                snippet=item.get("snippet", ""),
                url=link,
            )
        )
    return results


def job_search(query: str, *, limit: int = 5) -> list[SearchResult]:
    if not settings.job_search_engine_id:
        raise SearchError("JOB_SEARCH_ENGINE_ID is not configured")
    return custom_search(query, settings.job_search_engine_id, limit=limit)


def competitor_search(query: str, *, limit: int = 5) -> list[SearchResult]:
    if not settings.competitor_search_engine_id:
        raise SearchError("COMPETITOR_SEARCH_ENGINE_ID is not configured")
    return custom_search(query, settings.competitor_search_engine_id, limit=limit)
