#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
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
    utc_now,
    LoopError,
)


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def common_theme(goals: list[dict]) -> str:
    tokens: dict[str, int] = {}
    ignore = {
        "the",
        "and",
        "for",
        "with",
        "into",
        "from",
        "that",
        "this",
        "loop",
        "release",
        "kit",
        "add",
        "make",
        "use",
        "your",
        "next",
    }
    for goal in goals:
        words = re.findall(r"[a-z0-9]+", goal_title(goal).lower())
        seen: set[str] = set()
        for word in words:
            if len(word) < 4 or word in ignore or word in seen:
                continue
            seen.add(word)
            tokens[word] = tokens.get(word, 0) + 1
    if not tokens:
        return "the next user-visible improvement theme"
    return max(tokens.items(), key=lambda item: (item[1], item[0]))[0].replace("-", " ")


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


def pending_titles(backlog: list[dict], selected_goal_ids: list[str], limit: int = 3) -> list[str]:
    titles: list[str] = []
    for item in backlog:
        goal_id = str(item.get("id", "")).strip()
        if item.get("status", "pending") != "pending" or goal_id in selected_goal_ids:
            continue
        titles.append(goal_title(item))
        if len(titles) >= limit:
            break
    return titles


def aggregate_acceptance(goals: list[dict], limit: int = 6) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for goal in goals:
        for item in goal.get("acceptance", []):
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            lines.append(text)
            if len(lines) >= limit:
                return lines
    return lines


def build_release_brief(args: argparse.Namespace, goals: list[dict], backlog: list[dict]) -> dict:
    titles = [goal_title(goal) for goal in goals]
    theme = common_theme(goals)
    selected_goal_ids = [str(goal.get("id", "")).strip() for goal in goals]
    deferred = [str(item).strip() for item in args.deferred_item if str(item).strip()] or pending_titles(backlog, selected_goal_ids)
    release_acceptance = [str(item).strip() for item in args.release_acceptance if str(item).strip()] or aggregate_acceptance(goals)
    scope_in = [str(item).strip() for item in args.scope_in if str(item).strip()] or titles
    scope_out = [str(item).strip() for item in args.scope_out if str(item).strip()] or deferred
    objective = str(args.objective or f"Ship a coherent release around {theme}.").strip()
    target_user_value = str(
        args.target_user_value
        or "Users should experience one packaged improvement with a clear story instead of several disconnected tiny task commits."
    ).strip()
    why_now = str(
        args.why_now
        or "These bundled goals are the highest-value pending items that reinforce the same release theme and should land together now."
    ).strip()
    packaging_rationale = str(
        args.packaging_rationale
        or f"These goals all strengthen the same release theme around {theme}, so shipping them together creates a clearer user-visible version."
    ).strip()
    launch_story = str(
        args.launch_story
        or f"This release tells one simple story: {objective} It packages {len(titles)} aligned improvements into a single version."
    ).strip()
    return {
        "objective": objective,
        "target_user_value": target_user_value,
        "why_now": why_now,
        "packaging_rationale": packaging_rationale,
        "scope_in": scope_in,
        "scope_out": scope_out,
        "release_acceptance": release_acceptance,
        "launch_story": launch_story,
        "deferred_items": deferred,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle multiple pending goals into the next release version.")
    parser.add_argument("--goal-id", action="append", default=[], help="Explicit backlog goal id to include. Repeat as needed.")
    parser.add_argument("--title", help="Explicit release title.")
    parser.add_argument("--summary", help="Explicit release summary.")
    parser.add_argument("--count", type=int, help="How many pending goals to bundle when goal ids are not provided.")
    parser.add_argument("--objective", help="PM release objective for this bundled version.")
    parser.add_argument("--target-user-value", help="What user-visible value this release should create.")
    parser.add_argument("--why-now", help="Why this bundled release should happen now.")
    parser.add_argument("--packaging-rationale", help="Why these goals belong in one bundled release.")
    parser.add_argument("--scope-in", action="append", default=[], help="Explicit in-scope item for the bundled release. Repeat as needed.")
    parser.add_argument("--scope-out", action="append", default=[], help="Explicit out-of-scope item for the bundled release. Repeat as needed.")
    parser.add_argument("--release-acceptance", action="append", default=[], help="Release-level acceptance item. Repeat as needed.")
    parser.add_argument("--launch-story", help="Human-facing launch story for this release.")
    parser.add_argument("--deferred-item", action="append", default=[], help="Explicit deferred item that should stay out of the release. Repeat as needed.")
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
    brief = build_release_brief(args, goals, backlog)
    release_payload = {
        "number": release_number,
        "title": str(args.title or auto_title(release_number, goals)).strip(),
        "summary": str(args.summary or auto_summary(goals)).strip(),
        "status": "planned",
        "brief": brief,
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
            "objective": brief["objective"],
        },
    )

    if args.json:
        print(json.dumps(release_payload, ensure_ascii=True, indent=2))
    else:
        print(f"Planned release R{release_number}: {release_payload['title']}")
        print(f"- Objective: {brief['objective']}")
        print(f"- User value: {brief['target_user_value']}")
        print(f"- Why now: {brief['why_now']}")
        print(f"- Packaging rationale: {brief['packaging_rationale']}")
        for title in release_payload["goal_titles"]:
            print(f"- {title}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
