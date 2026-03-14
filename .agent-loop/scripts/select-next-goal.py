#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    LoopError,
    find_repo_root,
    goal_title,
    load_backlog,
    load_config,
    load_state,
    require_session_capacity,
    save_state,
    session_summary,
    utc_now,
)


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def pick_goal(backlog: list[dict]) -> dict:
    pending = [item for item in backlog if item.get("status", "pending") == "pending"]
    if not pending:
        raise LoopError("No pending backlog items remain.")
    pending.sort(key=lambda item: (PRIORITY_ORDER.get(item.get("priority", "medium"), 99), item.get("id", "")))
    return pending[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the next scoped goal for the autonomous loop.")
    parser.add_argument("--json", action="store_true", help="Print the full selected goal as JSON.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    backlog = load_backlog(root)
    state = load_state(root)
    session = require_session_capacity(config, state)
    selected = pick_goal(backlog)

    state["current_goal"] = {
        "id": selected.get("id"),
        "title": selected.get("title"),
        "priority": selected.get("priority", "medium"),
        "selected_at": utc_now(),
        "source": ".agent-loop/backlog.json",
    }
    state["status"] = "goal_selected"
    save_state(root, state)

    if args.json:
        print(json.dumps(selected, ensure_ascii=True, indent=2))
    else:
        progress = session_summary(state)
        suffix = ""
        if progress["target_iterations"] is not None:
            next_iteration = progress["completed_iterations"] + 1
            suffix = f" (session {next_iteration}/{progress['target_iterations']})"
        print(f"Selected goal: {goal_title(selected)}{suffix}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
