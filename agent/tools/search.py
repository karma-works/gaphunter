from __future__ import annotations

import httpx


class SearchError(RuntimeError):
    pass


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
        snippet = " ".join(s for s in snippets if s).strip()
        results.append({"title": title, "url": str(url), "snippet": snippet, "query": query})
    return results
