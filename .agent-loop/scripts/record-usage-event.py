#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import append_usage_log, kit_root, load_config, LoopError, project_root


def parse_fields(items: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise LoopError(f"Invalid --field value '{item}'. Expected key=value.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise LoopError(f"Invalid --field value '{item}'. Field name is required.")
        fields[key] = value
    return fields


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a lightweight usage event for the current or target repo.")
    parser.add_argument("--event", required=True, help="Usage event type to record.")
    parser.add_argument("--repo-root", help="Explicit workspace root. Defaults to the kit workspace root.")
    parser.add_argument("--target-root", help="Explicit target project root to record in the usage payload.")
    parser.add_argument("--field", action="append", default=[], help="Additional payload field in key=value form.")
    parser.add_argument("--json", action="store_true", help="Print the recorded event path and payload as JSON.")
    args = parser.parse_args()

    workspace_root = Path(args.repo_root).resolve() if args.repo_root else kit_root()
    target_root = Path(args.target_root).resolve() if args.target_root else project_root()
    config = load_config(kit_root())
    payload = parse_fields(list(args.field))
    log_path = append_usage_log(workspace_root, config, args.event, payload, target_root=target_root)
    result = {
        "event": args.event,
        "repo_root": str(workspace_root),
        "target_root": str(target_root),
        "log_path": str(log_path) if log_path else "",
        "payload": payload,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"Recorded usage event '{args.event}' at {result['log_path']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
