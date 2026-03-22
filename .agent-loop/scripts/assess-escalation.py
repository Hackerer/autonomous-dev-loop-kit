#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import assess_escalation, load_config, load_state, resolve_execution_roots, save_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess whether the current loop state should watch or escalate repeated failures.")
    parser.add_argument("--apply", action="store_true", help="Persist the assessed escalation result into review_state.escalation.")
    parser.add_argument("--json", action="store_true", help="Print the assessment as JSON.")
    args = parser.parse_args()

    kit_root, _, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    assessment = assess_escalation(config, state)

    if args.apply:
        review_state = state.get("review_state", {})
        if not isinstance(review_state, dict):
            review_state = {}
        review_state["escalation"] = assessment
        state["review_state"] = review_state
        save_state(workspace_root, state)

    if args.json:
        print(json.dumps(assessment, ensure_ascii=True, indent=2))
    else:
        print(f"Escalation status: {assessment['status']}")
        if assessment["reason"]:
            print(f"Reason: {assessment['reason']}")
        if assessment["recommended_action"]:
            print(f"Recommended action: {assessment['recommended_action']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - defensive CLI exit
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
