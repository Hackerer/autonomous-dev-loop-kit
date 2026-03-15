#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    append_usage_log,
    goal_title,
    find_repo_root,
    load_backlog,
    load_config,
    load_state,
    release_planning_config,
    release_summary,
    require_session_capacity,
    save_state,
    session_summary,
    utc_now,
    LoopError,
)


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def auto_title(number: int, goals: list[dict]) -> str:
    first = goal_title(goals[0]) if goals else f"Release {number}"
    if len(goals) <= 1:
        return f"R{number}: {first}"
    return f"R{number}: {first} + {len(goals) - 1} more bundled goals"


def auto_summary(goals: list[dict]) -> str:
    titles = [goal_title(goal) for goal in goals]
    if not titles:
        return ""
    if len(titles) == 1:
        return f"Ship the single high-priority goal `{titles[0]}` as a standalone bundled release."
    return "Bundle these goals into one user-facing release: " + "; ".join(titles)


def pick_pending(backlog: list[dict], count: int) -> list[dict]:
    pending = [item for item in backlog if item.get("status", "pending") == "pending"]
    pending.sort(key=lambda item: (PRIORITY_ORDER.get(item.get("priority", "medium"), 99), str(item.get("id", ""))))
    return pending[:count]


def resolve_goals(backlog: list[dict], goal_ids: list[str], count: int) -> list[dict]:
    if goal_ids:
        lookup = {str(item.get("id", "")): item for item in backlog}
        selected: list[dict] = []
        for goal_id in goal_ids:
            item = lookup.get(goal_id)
            if item is None:
                raise LoopError(f"Unknown backlog goal id: {goal_id}")
            if item.get("status", "pending") != "pending":
                raise LoopError(f"Backlog goal is not pending: {goal_id}")
            selected.append(item)
        return selected

    selected = pick_pending(backlog, count)
    if len(selected) < 1:
        raise LoopError("No pending backlog items remain to bundle into a release.")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle multiple pending goals into the next release version.")
    parser.add_argument("--goal-id", action="append", default=[], help="Explicit backlog goal id to include. Repeat as needed.")
    parser.add_argument("--title", help="Explicit release title.")
    parser.add_argument("--summary", help="Explicit release summary.")
    parser.add_argument("--count", type=int, help="How many pending goals to bundle when goal ids are not provided.")
    parser.add_argument("--json", action="store_true", help="Print the planned release as JSON.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    backlog = load_backlog(root)
    session = require_session_capacity(config, state)
    release_cfg = release_planning_config(config)
    current_release = release_summary(state)

    if current_release["status"] not in {"not_planned", "published"}:
        raise LoopError(
            "An active release already exists. Finish it with `write-release-report.py` and `publish-release.py`, "
            "or clear it intentionally before planning another release."
        )

    count = args.count or release_cfg["default_goals_per_release"]
    if count < release_cfg["min_goals_per_release"]:
        raise LoopError(
            f"--count must be at least {release_cfg['min_goals_per_release']} bundled goals for a release."
        )
    if count > release_cfg["max_goals_per_release"]:
        raise LoopError(
            f"--count must be at most {release_cfg['max_goals_per_release']} bundled goals for a release."
        )

    goals = resolve_goals(backlog, [str(goal_id) for goal_id in args.goal_id], count)
    release_number = int(session["completed_releases"] or 0) + 1
    release_payload = {
        "number": release_number,
        "title": str(args.title or auto_title(release_number, goals)).strip(),
        "summary": str(args.summary or auto_summary(goals)).strip(),
        "status": "planned",
        "goal_ids": [str(goal.get("id", "")) for goal in goals],
        "goal_titles": [goal_title(goal) for goal in goals],
        "completed_goal_ids": [],
        "task_iterations": [],
        "selected_at": utc_now(),
        "published_at": None,
        "report_path": None,
    }
    state["release"] = release_payload
    state["current_goal"] = None
    state["draft_goal"] = None
    state["draft_iteration"] = None
    state["draft_report"] = None
    state["draft_release_report"] = None
    state["status"] = "release_planned"
    save_state(root, state)

    append_usage_log(
        root,
        config,
        "release_planned",
        {
            "release_number": release_number,
            "title": release_payload["title"],
            "goal_ids": release_payload["goal_ids"],
        },
    )

    if args.json:
        print(json.dumps(release_payload, ensure_ascii=True, indent=2))
    else:
        print(f"Planned release R{release_number}: {release_payload['title']}")
        for title in release_payload["goal_titles"]:
            print(f"- {title}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
