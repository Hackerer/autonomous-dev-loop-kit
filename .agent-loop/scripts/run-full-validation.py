#!/usr/bin/env python3
from __future__ import annotations

import sys

from common import (
    LAST_VALIDATION_FILE,
    LoopError,
    find_repo_root,
    load_config,
    load_state,
    run_shell,
    save_json,
    save_state,
    utc_now,
)


def main() -> int:
    root = find_repo_root()
    config = load_config(root)
    validation = config.get("validation", {})
    commands = validation.get("commands", [])
    if not commands:
        raise LoopError("No validation.commands configured in .agent-loop/config.json")

    results = []
    passed = True
    for item in commands:
        name = item.get("name", "unnamed")
        command = item.get("command")
        required = bool(item.get("required", True))
        if not command:
            raise LoopError(f"Validation step '{name}' is missing a command")
        result = run_shell(command, root)
        result["name"] = name
        result["required"] = required
        result["passed"] = result["exit_code"] == 0
        results.append(result)
        if required and not result["passed"]:
            passed = False
            if validation.get("stop_on_first_failure", False):
                break

    summary = {"status": "passed" if passed else "failed", "ran_at": utc_now(), "results": results}
    save_json(root / ".agent-loop" / LAST_VALIDATION_FILE, summary)

    state = load_state(root)
    state["last_validation"] = summary
    state["status"] = "validated" if passed else "validation_failed"
    state["consecutive_failures"] = 0 if passed else int(state.get("consecutive_failures", 0)) + 1
    save_state(root, state)

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {result['name']}: {result['command']}")

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
