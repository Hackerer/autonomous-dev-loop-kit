#!/usr/bin/env python3
from __future__ import annotations

import sys

from common import (
    LoopError,
    find_repo_root,
    load_config,
    load_state,
    require_evaluator_pass,
    require_review_state,
)


def main() -> int:
    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    goal = state.get("current_goal") or state.get("draft_goal")

    review_state = require_review_state(config, state, goal)
    evaluation = review_state.get("evaluation", {}) if isinstance(review_state, dict) else {}
    evaluator = config.get("committee", {}).get("evaluator", {})
    gate_mode = str(evaluator.get("implementation_gate_mode", "blocking")).strip()

    if gate_mode == "advisory":
        result = evaluation.get("result", "pending") if isinstance(evaluation, dict) else "pending"
        if not isinstance(evaluation, dict) or evaluation.get("status") != "captured":
            raise LoopError(
                "Evaluator result has not been captured for the active goal. Record it before implementation, even in advisory mode."
            )
        if result != "pass":
            print(f"Implementation readiness advisory warning ({result}). Proceeding without blocking implementation.")
            return 0

    evaluation = require_evaluator_pass(config, state, goal)
    result = evaluation.get("result", "pass") if isinstance(evaluation, dict) else "pass"
    print(f"Implementation readiness confirmed ({result}, {gate_mode}).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
