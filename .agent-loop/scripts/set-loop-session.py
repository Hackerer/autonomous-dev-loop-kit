#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import append_usage_log, default_state, LoopError, find_repo_root, load_config, load_state, planning_config, save_state, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist the requested release count for the current autonomous session.")
    parser.add_argument("--iterations", type=int, required=True, help="How many bundled release versions this autonomous session may publish.")
    args = parser.parse_args()

    if args.iterations <= 0:
        raise LoopError("--iterations must be a positive integer")

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    planning = planning_config(config)
    max_allowed = planning.get("max_releases_per_session", planning.get("max_iterations_per_session"))
    if max_allowed is not None and args.iterations > int(max_allowed):
        raise LoopError(
            f"Requested {args.iterations} releases but config planning.max_releases_per_session only allows {int(max_allowed)}."
        )
    session_started_at = utc_now()
    session_id = f"session-{session_started_at.replace(':', '').replace('-', '').replace('T', '-').replace('Z', '')}"

    state["session"] = {
        "id": session_id,
        "status": "active",
        "target_releases": int(args.iterations),
        "completed_releases": 0,
        "target_iterations": None,
        "completed_iterations": 0,
        "started_at": session_started_at,
        "ended_at": None,
    }
    state["status"] = "session_configured"
    state["current_goal"] = None
    state["release"] = default_state()["release"]
    state["draft_iteration"] = None
    state["draft_report"] = None
    state["draft_release_report"] = None
    state["draft_goal"] = None
    state["review_state"] = default_state()["review_state"]
    state["consecutive_failures"] = 0
    save_state(root, state)
    append_usage_log(
        root,
        config,
        "session_started",
        {
            "session_id": session_id,
            "target_releases": int(args.iterations),
        },
    )

    print(f"Configured autonomous loop session for {args.iterations} release versions.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
