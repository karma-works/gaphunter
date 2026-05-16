from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy the GapHunter Agent Engine.")
    parser.add_argument("--project", default="gaphunter-496315")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument(
        "--staging-bucket",
        default="gs://gaphunter-agent-engine-staging-519220506089",
    )
    parser.add_argument("--display-name", default="gaphunter-agent-engine")
    parser.add_argument("--brave-search-api-key", default=None)
    parser.add_argument("--gemini-api-key", default=None)
    return parser.parse_args()


def main() -> None:
    import os

    args = parse_args()

    import vertexai
    from vertexai import agent_engines

    from agent.orchestrator import root_agent

    vertexai.init(
        project=args.project,
        location=args.location,
        staging_bucket=args.staging_bucket,
    )

    env_vars: dict[str, str] = {
        "GCP_PROJECT_ID": args.project,
        "FIRESTORE_COLLECTION": "runs",
    }
    brave_key = args.brave_search_api_key or os.getenv("BRAVE_SEARCH_API_KEY")
    gemini_key = args.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise SystemExit(
            "GEMINI_API_KEY is required for Phase 6b Agent Engine deployment. "
            "Production runs do not use deterministic Gemini fallback."
        )
    if brave_key:
        env_vars["BRAVE_SEARCH_API_KEY"] = brave_key
    env_vars["GEMINI_API_KEY"] = gemini_key

    remote_agent = agent_engines.create(
        root_agent,
        requirements="agent/requirements.txt",
        extra_packages=["agent"],
        env_vars=env_vars,
        display_name=args.display_name,
        description="GapHunter research agent — Phase 6b.",
    )
    print(remote_agent.resource_name)


if __name__ == "__main__":
    main()
