from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.search import SearchError, brave_search, competitor_search, custom_search, job_search


def _brave_settings(**overrides):
    base = dict(
        brave_search_api_key="test-key",
        brave_search_country="US",
        brave_search_lang="en",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _custom_settings(**overrides):
    base = dict(
        custom_search_api_key="test-key",
        job_search_engine_id="job-cx",
        competitor_search_engine_id="comp-cx",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


def _brave_payload():
    return {
        "web": {
            "results": [
                {
                    "title": "Tender Specialist",
                    "url": "https://example.com/job",
                    "description": "Reviews tenders.",
                    "extra_snippets": ["Drafts memos."],
                }
            ]
        }
    }


def _custom_payload():
    return {
        "items": [
            {
                "title": "Custom Result",
                "link": "https://example.com/custom",
                "snippet": "A custom search result.",
            }
        ]
    }


def test_brave_search_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("app.search.settings", _brave_settings(brave_search_api_key=None))

    with pytest.raises(SearchError, match="BRAVE_SEARCH_API_KEY"):
        brave_search("test query")


def test_brave_search_raises_on_http_error(monkeypatch):
    monkeypatch.setattr("app.search.settings", _brave_settings())
    monkeypatch.setattr("app.search.httpx.get", lambda *a, **kw: FakeResponse(429, {}))

    with pytest.raises(SearchError, match="HTTP 429"):
        brave_search("test query")


def test_custom_search_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("app.search.settings", _custom_settings(custom_search_api_key=None))

    with pytest.raises(SearchError, match="GOOGLE_CUSTOM_SEARCH_API_KEY"):
        custom_search("test query", "cx-id")


def test_custom_search_raises_on_http_error(monkeypatch):
    monkeypatch.setattr("app.search.settings", _custom_settings())
    monkeypatch.setattr("app.search.httpx.get", lambda *a, **kw: FakeResponse(403, {}))

    with pytest.raises(SearchError, match="HTTP 403"):
        custom_search("test query", "cx-id")


def test_custom_search_normalizes_results(monkeypatch):
    monkeypatch.setattr("app.search.settings", _custom_settings())
    monkeypatch.setattr("app.search.httpx.get", lambda *a, **kw: FakeResponse(200, _custom_payload()))

    results = custom_search("test query", "cx-id")

    assert len(results) == 1
    assert results[0].title == "Custom Result"
    assert str(results[0].url) == "https://example.com/custom"
    assert results[0].snippet == "A custom search result."


def test_custom_search_drops_items_without_link(monkeypatch):
    monkeypatch.setattr("app.search.settings", _custom_settings())
    payload = {"items": [{"title": "No link here", "snippet": "whatever"}]}
    monkeypatch.setattr("app.search.httpx.get", lambda *a, **kw: FakeResponse(200, payload))

    assert custom_search("test", "cx-id") == []


def test_job_search_routes_to_brave(monkeypatch):
    calls = []
    monkeypatch.setattr("app.search.settings", SimpleNamespace(search_provider="brave"))
    monkeypatch.setattr(
        "app.search.brave_search",
        lambda q, **kw: (calls.append(q) or []),
    )

    job_search("tender ops")

    assert calls == ["tender ops"]


def test_job_search_routes_to_custom_search(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.search.settings",
        SimpleNamespace(
            search_provider="custom_search",
            job_search_engine_id="job-cx",
        ),
    )
    monkeypatch.setattr(
        "app.search.custom_search",
        lambda q, cx, **kw: (calls.append((q, cx)) or []),
    )

    job_search("tender ops")

    assert calls == [("tender ops", "job-cx")]


def test_job_search_raises_on_unknown_provider(monkeypatch):
    monkeypatch.setattr("app.search.settings", SimpleNamespace(search_provider="openai_search"))

    with pytest.raises(SearchError, match="openai_search"):
        job_search("tender ops")


def test_job_search_raises_when_custom_search_engine_id_missing(monkeypatch):
    monkeypatch.setattr(
        "app.search.settings",
        SimpleNamespace(search_provider="custom_search", job_search_engine_id=None),
    )

    with pytest.raises(SearchError, match="JOB_SEARCH_ENGINE_ID"):
        job_search("tender ops")


def test_competitor_search_routes_to_brave(monkeypatch):
    calls = []
    monkeypatch.setattr("app.search.settings", SimpleNamespace(search_provider="brave"))
    monkeypatch.setattr(
        "app.search.brave_search",
        lambda q, **kw: (calls.append(q) or []),
    )

    competitor_search("AI agent for tender ops")

    assert calls == ["AI agent for tender ops"]


def test_competitor_search_raises_when_engine_id_missing(monkeypatch):
    monkeypatch.setattr(
        "app.search.settings",
        SimpleNamespace(search_provider="custom_search", competitor_search_engine_id=None),
    )

    with pytest.raises(SearchError, match="COMPETITOR_SEARCH_ENGINE_ID"):
        competitor_search("AI agent for tender ops")
