#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from common import (
    LoopError,
    find_repo_root,
    goal_title,
    load_config,
    load_state,
    relpath,
    reporting_path,
    require_green_validation,
    save_state,
    session_summary,
)


def bullet_lines(values: list[str], fallback: str) -> list[str]:
    if not values:
        return [f"- {fallback}"]
    return [f"- {value}" for value in values]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a version report for the next autonomous iteration.")
    parser.add_argument("--analysis", action="append", default=[], help="Current-state analysis bullet.")
    parser.add_argument("--acceptance", action="append", default=[], help="Acceptance bullet for this version.")
    parser.add_argument("--observation", action="append", default=[], help="Key observation bullet from the ReAct cycle.")
    parser.add_argument("--delivered", action="append", default=[], help="Delivered change bullet.")
    parser.add_argument("--reflection", action="append", default=[], help="Reflection bullet.")
    parser.add_argument("--next-goal", action="append", default=[], help="Next-goal proposal bullet.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    validation = require_green_validation(state)
    session = session_summary(state)

    iteration = int(state.get("iteration", 0)) + 1
    report_path = reporting_path(root, config, iteration)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    goal = state.get("current_goal")
    goal_label = goal_title(goal)
    today = datetime.now().date().isoformat()

    validation_lines = []
    for result in validation.get("results", []):
        status = "PASS" if result.get("passed") else "FAIL"
        validation_lines.append(f"- `{result.get('command')}` -> {status} (exit {result.get('exit_code')})")
    if not validation_lines:
        validation_lines = ["- No validation results were recorded."]

    content = [
        f"# v{iteration} Report",
        "",
        f"Date: {today}",
        "",
        "## Session Progress",
        (
            f"- Session progress: {session['completed_iterations'] + 1}/{session['target_iterations']}"
            if session["target_iterations"] is not None
            else "- Session progress: unbounded session"
        ),
        "",
        "## Current State Analysis",
        *bullet_lines(args.analysis, "Summarize the current repo state before this version."),
        "",
        "## Version Goal",
        f"- Goal: {goal_label}",
        *bullet_lines(args.acceptance, "Document the acceptance criteria for this version."),
        "",
        "## Key Observations",
        *bullet_lines(args.observation, "Capture the evidence or observation that most influenced this version."),
        "",
        "## Delivered",
        *bullet_lines(args.delivered, "List the concrete changes delivered in this version."),
        "",
        "## Full Validation",
        *validation_lines,
        "",
        "## Reflection",
        *bullet_lines(args.reflection, "Reflect on requirement clarity and architectural impact."),
        "",
        "## Proposed Next Goal",
        *bullet_lines(args.next_goal, "Propose the next highest-value small version."),
        "",
    ]
    report_path.write_text("\n".join(content), encoding="utf-8")

    state = load_state(root)
    state["draft_iteration"] = iteration
    state["draft_report"] = relpath(report_path, root)
    state["draft_goal"] = goal
    state["status"] = "report_written"
    save_state(root, state)

    print(report_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
