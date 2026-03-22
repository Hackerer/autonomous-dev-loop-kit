#!/usr/bin/env python3
from __future__ import annotations

import sys

from common import (
    implementation_gate_status,
    LoopError,
    load_config,
    load_state,
    require_evaluator_pass,
    require_review_state,
    resolve_execution_roots,
)


def main() -> int:
    kit_root, _, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    goal = state.get("current_goal") or state.get("draft_goal")

    review_state = require_review_state(config, state, goal)
    evaluation = review_state.get("evaluation", {}) if isinstance(review_state, dict) else {}
    gate = implementation_gate_status(config, evaluation if isinstance(evaluation, dict) else {})
    gate_mode = gate["mode"]

    if gate_mode == "advisory":
        result = gate["evaluation_result"]
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
