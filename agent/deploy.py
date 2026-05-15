from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy the GapHunter Agent Engine spike.")
    parser.add_argument("--project", default="gaphunter-496315")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument(
        "--staging-bucket",
        default="gs://gaphunter-agent-engine-staging-519220506089",
    )
    parser.add_argument("--display-name", default="gaphunter-agent-engine-spike")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import vertexai
    from vertexai import agent_engines

    from agent.orchestrator import root_agent

    vertexai.init(
        project=args.project,
        location=args.location,
        staging_bucket=args.staging_bucket,
    )
    remote_agent = agent_engines.create(
        root_agent,
        requirements="agent/requirements.txt",
        extra_packages=["agent"],
        env_vars={"GCP_PROJECT_ID": args.project, "FIRESTORE_COLLECTION": "runs"},
        display_name=args.display_name,
        description="GapHunter deterministic Agent Engine deployment spike.",
    )
    print(remote_agent.resource_name)


if __name__ == "__main__":
    main()
