#!/usr/bin/env python3
from __future__ import annotations

import sys

from common import (
    LAST_VALIDATION_FILE,
    append_usage_log,
    LoopError,
    load_config,
    load_state,
    run_shell,
    save_json,
    save_state,
    resolve_execution_roots,
    utc_now,
)


def main() -> int:
    kit_root, target_root, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
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
        result = run_shell(command, target_root)
        result["name"] = name
        result["required"] = required
        result["passed"] = result["exit_code"] == 0
        results.append(result)
        if required and not result["passed"]:
            passed = False
            if validation.get("stop_on_first_failure", False):
                break

    summary = {"status": "passed" if passed else "failed", "ran_at": utc_now(), "results": results}
    save_json(workspace_root / ".agent-loop" / LAST_VALIDATION_FILE, summary)

    state = load_state(workspace_root)
    state["last_validation"] = summary
    state["status"] = "validated" if passed else "validation_failed"
    state["consecutive_failures"] = 0 if passed else int(state.get("consecutive_failures", 0)) + 1
    save_state(workspace_root, state)
    append_usage_log(
        workspace_root,
        config,
        "validation_passed" if passed else "validation_failed",
        {
            "required_failures": [
                result["name"] for result in results if result.get("required") and not result.get("passed")
            ],
            "result_count": len(results),
        },
        target_root=target_root,
    )

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
