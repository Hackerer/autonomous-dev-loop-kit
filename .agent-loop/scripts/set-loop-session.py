#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import LoopError, find_repo_root, load_config, load_state, planning_config, save_state, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist the requested loop count for the current autonomous session.")
    parser.add_argument("--iterations", type=int, required=True, help="How many versions this autonomous session may publish.")
    args = parser.parse_args()

    if args.iterations <= 0:
        raise LoopError("--iterations must be a positive integer")

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    planning = planning_config(config)
    max_allowed = planning.get("max_iterations_per_session")
    if max_allowed is not None and args.iterations > int(max_allowed):
        raise LoopError(
            f"Requested {args.iterations} iterations but config planning.max_iterations_per_session only allows {int(max_allowed)}."
        )

    state["session"] = {
        "status": "active",
        "target_iterations": int(args.iterations),
        "completed_iterations": 0,
        "started_at": utc_now(),
        "ended_at": None,
    }
    state["status"] = "session_configured"
    state["current_goal"] = None
    state["draft_iteration"] = None
    state["draft_report"] = None
    state["draft_goal"] = None
    save_state(root, state)

    print(f"Configured autonomous loop session for {args.iterations} iterations.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
