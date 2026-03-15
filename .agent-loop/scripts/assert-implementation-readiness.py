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

    require_review_state(config, state, goal)
    evaluation = require_evaluator_pass(config, state, goal)

    result = evaluation.get("result", "pass") if isinstance(evaluation, dict) else "pass"
    print(f"Implementation readiness confirmed ({result}).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
