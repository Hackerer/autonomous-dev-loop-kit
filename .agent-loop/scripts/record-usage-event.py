#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import append_usage_log, find_repo_root, load_config, LoopError


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
    parser.add_argument("--repo-root", help="Explicit target repo root. Defaults to the current repo root.")
    parser.add_argument("--field", action="append", default=[], help="Additional payload field in key=value form.")
    parser.add_argument("--json", action="store_true", help="Print the recorded event path and payload as JSON.")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root()
    config = load_config(root)
    payload = parse_fields(list(args.field))
    log_path = append_usage_log(root, config, args.event, payload)
    result = {
        "event": args.event,
        "repo_root": str(root),
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
