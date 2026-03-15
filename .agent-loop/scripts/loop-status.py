#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    find_repo_root,
    goal_title,
    implementation_gate_status,
    load_config,
    load_state,
    release_summary,
    review_state_matches_goal,
    session_summary,
    LoopError,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the current autonomous loop session, release, and gate status.")
    parser.add_argument("--json", action="store_true", help="Print the status payload as JSON.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    session = session_summary(state)
    release = release_summary(state)
    goal = state.get("current_goal") or state.get("draft_goal")
    review_state = state.get("review_state", {})
    review_matches = review_state_matches_goal(review_state, goal)
    evaluation = review_state.get("evaluation", {}) if isinstance(review_state, dict) else {}
    validation = state.get("last_validation", {})

    payload = {
        "repo_root": str(root),
        "state_status": state.get("status"),
        "session": session,
        "release": release,
        "goal": {
            "id": goal.get("id"),
            "title": goal_title(goal),
        }
        if isinstance(goal, dict)
        else None,
        "review": {
            "status": review_state.get("status") if isinstance(review_state, dict) else "not_started",
            "matches_active_goal": review_matches,
            "goal_id": review_state.get("goal_id") if isinstance(review_state, dict) else None,
            "goal_title": review_state.get("goal_title") if isinstance(review_state, dict) else None,
        },
        "implementation_gate": implementation_gate_status(config, evaluation if isinstance(evaluation, dict) else {}),
        "validation": {
            "status": validation.get("status"),
            "ran_at": validation.get("ran_at"),
        }
        if isinstance(validation, dict)
        else {"status": "not_run", "ran_at": None},
        "drafts": {
            "draft_iteration": state.get("draft_iteration"),
            "draft_report": state.get("draft_report"),
            "draft_release_report": state.get("draft_release_report"),
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    print("Loop status")
    print(f"- State: {payload['state_status']}")
    print(
        f"- Session: {session['status']} "
        f"({session['completed_releases']}/{session['target_releases']} releases, "
        f"{session['completed_iterations']} task iterations)"
        if session["target_releases"] is not None
        else f"- Session: {session['status']}"
    )
    if release["number"] is not None:
        print(
            f"- Active release: R{release['number']} {release['title']} "
            f"({len(release['completed_goal_ids'])}/{len(release['goal_ids'])} tasks complete)"
        )
    else:
        print("- Active release: none")
    print(f"- Active goal: {goal_title(goal)}")
    print(f"- Review state: {payload['review']['status']} (matches active goal: {review_matches})")
    gate = payload["implementation_gate"]
    print(f"- Implementation gate: {gate['status']} ({gate['mode']}, evaluator {gate['evaluation_result']})")
    validation_payload = payload["validation"]
    print(f"- Last validation: {validation_payload['status']} at {validation_payload['ran_at']}")
    drafts = payload["drafts"]
    print(f"- Draft task report: {drafts['draft_report'] or 'none'}")
    print(f"- Draft release report: {drafts['draft_release_report'] or 'none'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
