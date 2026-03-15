#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from common import find_repo_root, load_config, usage_log_path, LoopError


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one or more autonomous loop usage-log files.")
    parser.add_argument("--repo", action="append", default=[], help="Repo root whose usage log should be analyzed.")
    parser.add_argument("--log", action="append", default=[], help="Explicit usage-log JSONL path.")
    parser.add_argument("--json", action="store_true", help="Print the usage summary as JSON.")
    args = parser.parse_args()

    log_paths: list[Path] = []
    for repo_root in args.repo:
        repo = Path(repo_root).resolve()
        config = load_config(repo)
        log_paths.append(usage_log_path(repo, config))
    for log_path in args.log:
        log_paths.append(Path(log_path).resolve())
    if not log_paths:
        root = find_repo_root()
        config = load_config(root)
        log_paths.append(usage_log_path(root, config))

    rows: list[dict] = []
    for path in log_paths:
        for row in load_jsonl(path):
            row["_log_path"] = str(path)
            rows.append(row)

    events = Counter(str(row.get("event", "")) for row in rows)
    repos = Counter(str(row.get("repo", {}).get("name", "")) for row in rows if isinstance(row.get("repo"), dict))
    summary = {
        "log_paths": [str(path) for path in log_paths],
        "event_count": len(rows),
        "events_by_type": dict(events),
        "events_by_repo": dict(repos),
        "last_event": rows[-1] if rows else None,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        return 0

    print("Usage log summary")
    print(f"- Total events: {summary['event_count']}")
    print("- Events by type:")
    if summary["events_by_type"]:
        for event_type, count in summary["events_by_type"].items():
            print(f"  - {event_type}: {count}")
    else:
        print("  - none")
    print("- Events by repo:")
    if summary["events_by_repo"]:
        for repo_name, count in summary["events_by_repo"].items():
            print(f"  - {repo_name}: {count}")
    else:
        print("  - none")
    if summary["last_event"]:
        last_event = summary["last_event"]
        print(f"- Last event: {last_event.get('event')} at {last_event.get('timestamp')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
