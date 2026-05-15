from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gcp_project_id: str | None = os.getenv("GCP_PROJECT_ID")
    firestore_collection: str = os.getenv("FIRESTORE_COLLECTION", "runs")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    search_provider: str = os.getenv("SEARCH_PROVIDER", "brave").lower()
    brave_search_api_key: str | None = os.getenv("BRAVE_SEARCH_API_KEY")
    brave_search_country: str = os.getenv("BRAVE_SEARCH_COUNTRY", "US")
    brave_search_lang: str = os.getenv("BRAVE_SEARCH_LANG", "en")
    custom_search_api_key: str | None = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
    job_search_engine_id: str | None = os.getenv("JOB_SEARCH_ENGINE_ID")
    competitor_search_engine_id: str | None = os.getenv("COMPETITOR_SEARCH_ENGINE_ID")
    agent_backend: str = os.getenv("AGENT_BACKEND", "local").lower()
    agent_engine_resource_name: str | None = os.getenv("AGENT_ENGINE_RESOURCE_NAME")
    agent_engine_location: str = os.getenv("AGENT_ENGINE_LOCATION", "us-central1")
    max_search_queries_per_run: int = int(os.getenv("MAX_SEARCH_QUERIES_PER_RUN", "20"))
    max_gemini_calls_per_run: int = int(os.getenv("MAX_GEMINI_CALLS_PER_RUN", "50"))

    @property
    def live_search_enabled(self) -> bool:
        if self.search_provider == "brave":
            return bool(self.brave_search_api_key)
        if self.search_provider == "custom_search":
            return bool(
                self.custom_search_api_key
                and self.job_search_engine_id
                and self.competitor_search_engine_id
            )
        return False

    @property
    def live_research_enabled(self) -> bool:
        return self.live_search_enabled


settings = Settings()
