#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import LoopError, find_repo_root, load_state, save_state, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist research and committee review conclusions for the current iteration.")
    parser.add_argument("--research", action="append", default=[], help="Research finding to persist.")
    parser.add_argument("--committee-feedback", action="append", default=[], help="Committee feedback bullet to persist.")
    parser.add_argument("--decision", action="append", default=[], help="Committee decision bullet to persist.")
    parser.add_argument("--reflection", action="append", default=[], help="Optional reflection bullet to persist.")
    parser.add_argument("--json", action="store_true", help="Print the captured review payload as JSON.")
    parser.add_argument("--no-state", action="store_true", help="Validate and print the payload without updating state.")
    args = parser.parse_args()

    if not args.research and not args.committee_feedback and not args.decision and not args.reflection:
        raise LoopError("At least one review input is required.")

    root = find_repo_root()
    state = load_state(root)
    goal = state.get("current_goal")
    payload = {
        "goal_id": goal.get("id") if isinstance(goal, dict) else None,
        "goal_title": goal.get("title") if isinstance(goal, dict) else None,
        "captured_at": utc_now(),
        "research_findings": list(args.research),
        "committee_feedback": list(args.committee_feedback),
        "committee_decision": list(args.decision),
        "reflection_notes": list(args.reflection),
        "status": "captured",
    }

    if not args.no_state:
        state["review_state"] = payload
        state["status"] = "review_captured"
        save_state(root, state)

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print("Captured review state.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
