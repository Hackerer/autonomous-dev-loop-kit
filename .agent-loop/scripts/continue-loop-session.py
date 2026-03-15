#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import LoopError, find_repo_root, load_config, load_state, planning_config, save_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Extend the current autonomous loop session without resetting progress.")
    parser.add_argument("--iterations", type=int, help="Set a new total target iteration count for the active session.")
    parser.add_argument("--add", type=int, help="Add this many iterations to the current session target.")
    args = parser.parse_args()

    if args.iterations is None and args.add is None:
        raise LoopError("Provide either --iterations or --add.")
    if args.iterations is not None and args.add is not None:
        raise LoopError("Use either --iterations or --add, not both.")
    if args.add is not None and args.add <= 0:
        raise LoopError("--add must be a positive integer.")
    if args.iterations is not None and args.iterations <= 0:
        raise LoopError("--iterations must be a positive integer.")

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    planning = planning_config(config)
    max_allowed = planning.get("max_iterations_per_session")

    session = state.get("session", {})
    if not isinstance(session, dict) or session.get("status") not in {"active", "completed"}:
        raise LoopError("No configured session exists to continue. Run `python3 .agent-loop/scripts/set-loop-session.py --iterations N` first.")

    completed = int(session.get("completed_iterations", 0) or 0)
    current_target = session.get("target_iterations")
    if current_target is None:
        raise LoopError("The current session does not have a target_iterations value to extend.")

    next_target = int(args.iterations) if args.iterations is not None else int(current_target) + int(args.add)
    if next_target <= completed:
        raise LoopError(f"New session target must be greater than completed progress ({completed}).")
    if max_allowed is not None and next_target > int(max_allowed):
        raise LoopError(
            f"Requested {next_target} total iterations but config planning.max_iterations_per_session only allows {int(max_allowed)}."
        )

    state["session"]["target_iterations"] = next_target
    state["session"]["status"] = "active"
    state["session"]["ended_at"] = None
    if state.get("status") == "session_completed":
        state["status"] = "published"
    save_state(root, state)

    print(f"Extended autonomous loop session to {next_target} total iterations (completed {completed}).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
