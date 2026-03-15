#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    LoopError,
    committee_config,
    evaluator_summary,
    find_repo_root,
    goal_title,
    load_config,
    load_json,
    load_state,
    require_review_state,
)


def build_project_context(root, state: dict) -> dict:
    project_data = state.get("project_data", {})
    snapshot_path = project_data.get("snapshot_path")
    snapshot = {}
    if snapshot_path:
        snapshot_file = root / snapshot_path
        if snapshot_file.exists():
            snapshot = load_json(snapshot_file, default={})

    repo = snapshot.get("repo", {}) if isinstance(snapshot, dict) else {}
    product_context = snapshot.get("product_context", {}) if isinstance(snapshot, dict) else {}
    validation = snapshot.get("validation", {}) if isinstance(snapshot, dict) else {}

    return {
        "target_outcome": str(product_context.get("target_outcome", "")),
        "constraints": list(product_context.get("constraints", [])) if isinstance(product_context.get("constraints"), list) else [],
        "current_branch": str(repo.get("current_branch", "")),
        "quality_status": project_data.get("last_quality_status"),
        "validation_commands": list(validation.get("configured_commands", []))
        if isinstance(validation.get("configured_commands"), list)
        else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the independent evaluator brief for the active goal.")
    parser.add_argument("--json", action="store_true", help="Print the evaluator brief as JSON.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    goal = state.get("current_goal")
    if not goal:
        raise LoopError("No active goal is selected. Run `python3 .agent-loop/scripts/select-next-goal.py` first.")

    review_state = require_review_state(config, state, goal)
    scope_decision = review_state.get("scope_decision", {})
    if not isinstance(scope_decision, dict) or scope_decision.get("status") != "captured":
        raise LoopError(
            "Scope decision is missing for the active goal. Capture it with `python3 .agent-loop/scripts/capture-review.py ... --selected-goal ...` before rendering the evaluator brief."
        )

    committee = committee_config(config)
    evaluator = committee.get("evaluator", {})
    rubric_ref = str(evaluator.get("rubric_ref", "")).strip() if isinstance(evaluator, dict) else ""
    if not rubric_ref:
        raise LoopError("Evaluator rubric is not configured in .agent-loop/config.json")

    rubric = load_json(root / rubric_ref)
    payload = {
        "goal": {
            "id": goal.get("id"),
            "title": goal_title(goal),
        },
        "scope_decision": {
            "selected_goal": scope_decision.get("selected_goal", ""),
            "why_selected": scope_decision.get("why_selected", ""),
            "scope_in": list(scope_decision.get("scope_in", [])),
            "scope_out": list(scope_decision.get("scope_out", [])),
            "assumptions": list(scope_decision.get("assumptions", [])),
            "risks": list(scope_decision.get("risks", [])),
            "required_validation": list(scope_decision.get("required_validation", [])),
            "stop_conditions": list(scope_decision.get("stop_conditions", [])),
        },
        "project_context": build_project_context(root, state),
        "evaluator": evaluator_summary(config),
        "rubric": rubric,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    persona = payload["evaluator"].get("persona", {})
    print("Independent evaluator brief")
    print(f"- Goal: {payload['goal']['title']}")
    print(f"- Evaluator: {persona.get('label', 'unconfigured evaluator')}")
    print(f"- Rubric: {rubric_ref}")
    print(f"- Target outcome: {payload['project_context'].get('target_outcome', '') or 'not captured'}")
    print(f"- Current branch: {payload['project_context'].get('current_branch', '') or 'unknown'}")
    print("- Scope in:")
    for item in payload["scope_decision"]["scope_in"] or ["No scope-in items recorded."]:
        print(f"  - {item}")
    print("- Scope out:")
    for item in payload["scope_decision"]["scope_out"] or ["No scope-out items recorded."]:
        print(f"  - {item}")
    print("- Required validation:")
    for item in payload["scope_decision"]["required_validation"] or ["No required validation recorded."]:
        print(f"  - {item}")
    print("- Rubric criteria:")
    for criterion, details in payload["rubric"].get("criteria", {}).items():
        question = details.get("question", "")
        weight = details.get("weight", "")
        print(f"  - {criterion} ({weight}): {question}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
