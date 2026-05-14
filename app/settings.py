from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gcp_project_id: str | None = os.getenv("GCP_PROJECT_ID")
    firestore_collection: str = os.getenv("FIRESTORE_COLLECTION", "runs")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    custom_search_api_key: str | None = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
    job_search_engine_id: str | None = os.getenv("JOB_SEARCH_ENGINE_ID")
    competitor_search_engine_id: str | None = os.getenv("COMPETITOR_SEARCH_ENGINE_ID")

    @property
    def live_search_enabled(self) -> bool:
        return bool(
            self.custom_search_api_key
            and self.job_search_engine_id
            and self.competitor_search_engine_id
        )

    @property
    def live_research_enabled(self) -> bool:
        return self.live_search_enabled


settings = Settings()
