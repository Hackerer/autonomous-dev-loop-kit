#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from common import find_repo_root, load_config, usage_log_path, LoopError


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    invalid_rows = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid_rows += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, invalid_rows


def parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min


def normalize_rows(log_paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    invalid_rows_by_path: dict[str, int] = {}
    for path in log_paths:
        loaded_rows, invalid_rows = load_jsonl(path)
        invalid_rows_by_path[str(path)] = invalid_rows
        for row in loaded_rows:
            row["_log_path"] = str(path)
            rows.append(row)
    rows.sort(key=lambda item: (parse_timestamp(item.get("timestamp")), str(item.get("_log_path", ""))))
    return rows, invalid_rows_by_path


def session_id_for(row: dict[str, Any]) -> str | None:
    session = row.get("session", {})
    if isinstance(session, dict):
        raw_session_id = session.get("id")
        session_id = str(raw_session_id).strip() if raw_session_id is not None else ""
        if session_id and session_id.lower() != "none":
            return session_id
    payload = row.get("payload", {})
    if isinstance(payload, dict):
        raw_session_id = payload.get("session_id")
        session_id = str(raw_session_id).strip() if raw_session_id is not None else ""
        if session_id and session_id.lower() != "none":
            return session_id
    return None


def summarize_session(session_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    events = Counter(str(row.get("event", "")) for row in rows)
    release_numbers_seen: list[int] = []
    planned_release_numbers: list[int] = []
    published_release_numbers: list[int] = []
    orphan_iterations: list[dict[str, Any]] = []
    stop_reasons: list[str] = []
    failure_events: list[str] = []
    clients = Counter(str(row.get("client", "") or "unknown") for row in rows)

    for row in rows:
        release = row.get("release", {})
        payload = row.get("payload", {})
        event = str(row.get("event", ""))
        release_number = None
        if isinstance(payload, dict) and payload.get("release_number") is not None:
            release_number = payload.get("release_number")
        elif isinstance(release, dict) and release.get("number") is not None:
            release_number = release.get("number")
        try:
            release_number_int = int(release_number) if release_number is not None else None
        except (TypeError, ValueError):
            release_number_int = None
        if release_number_int is not None:
            release_numbers_seen.append(release_number_int)
            if event == "release_planned":
                planned_release_numbers.append(release_number_int)
            if event == "release_published":
                published_release_numbers.append(release_number_int)

        if event == "iteration_published":
            goal = row.get("goal", {})
            goal_id = ""
            if isinstance(payload, dict):
                goal_id = str(payload.get("goal_id", "")).strip()
            if not goal_id and isinstance(goal, dict):
                goal_id = str(goal.get("id", "")).strip()
            if release_number_int is None or not goal_id:
                orphan_iterations.append(
                    {
                        "timestamp": row.get("timestamp"),
                        "iteration": row.get("iteration"),
                        "goal_id": goal_id,
                        "goal_title": (goal.get("title") if isinstance(goal, dict) else None) or payload.get("goal", ""),
                    }
                )

        if event in {"validation_failed", "implementation_blocked", "goal_selection_blocked"}:
            failure_events.append(event)
        if isinstance(payload, dict):
            reason = str(payload.get("stop_reason", "")).strip()
            if reason:
                stop_reasons.append(reason)

    unique_release_numbers = sorted(set(release_numbers_seen))
    release_number_gaps: list[str] = []
    if unique_release_numbers:
        expected = list(range(unique_release_numbers[0], unique_release_numbers[-1] + 1))
        missing = [number for number in expected if number not in unique_release_numbers]
        if missing:
            release_number_gaps.append(
                f"Missing release numbers in session {session_id}: {', '.join(str(number) for number in missing)}"
            )

    unpublished_plans = sorted(set(planned_release_numbers) - set(published_release_numbers))
    suspicious_patterns = list(release_number_gaps)
    if unpublished_plans:
        suspicious_patterns.append(
            f"Planned releases without publish closeout in session {session_id}: {', '.join(str(number) for number in unpublished_plans)}"
        )
    if orphan_iterations:
        suspicious_patterns.append(f"Session {session_id} contains {len(orphan_iterations)} orphan iteration publish events.")

    first = rows[0] if rows else {}
    last = rows[-1] if rows else {}
    session_context = first.get("session", {}) if isinstance(first.get("session"), dict) else {}

    return {
        "session_id": session_id,
        "repo": first.get("repo", {}).get("name", "") if isinstance(first.get("repo"), dict) else "",
        "started_at": first.get("timestamp"),
        "last_event_at": last.get("timestamp"),
        "status": last.get("state_status") or session_context.get("status"),
        "target_releases": session_context.get("target_releases"),
        "completed_releases": last.get("session", {}).get("completed_releases") if isinstance(last.get("session"), dict) else None,
        "completed_iterations": last.get("session", {}).get("completed_iterations") if isinstance(last.get("session"), dict) else None,
        "events_by_type": dict(events),
        "events_by_client": dict(clients),
        "planned_release_numbers": sorted(set(planned_release_numbers)),
        "published_release_numbers": sorted(set(published_release_numbers)),
        "orphan_iterations": orphan_iterations,
        "failure_events": failure_events,
        "stop_reasons": sorted(set(stop_reasons)),
        "suspicious_patterns": suspicious_patterns,
    }


def summarize_usage(rows: list[dict[str, Any]], log_paths: list[Path], invalid_rows_by_path: dict[str, int]) -> dict[str, Any]:
    events = Counter(str(row.get("event", "")) for row in rows)
    repos = Counter(str(row.get("repo", {}).get("name", "")) for row in rows if isinstance(row.get("repo"), dict))
    clients = Counter(str(row.get("client", "") or "unknown") for row in rows)

    session_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    legacy_rows: list[dict[str, Any]] = []
    for row in rows:
        session_id = session_id_for(row)
        if session_id:
            session_rows[session_id].append(row)
        else:
            legacy_rows.append(row)

    sessions = [summarize_session(session_id, items) for session_id, items in sorted(session_rows.items())]
    suspicious_patterns: list[str] = []
    for session in sessions:
        suspicious_patterns.extend(session.get("suspicious_patterns", []))
    if legacy_rows:
        suspicious_patterns.append(
            f"{len(legacy_rows)} legacy events do not include a session_id, so per-session attribution is incomplete."
        )
    invalid_row_count = sum(int(count) for count in invalid_rows_by_path.values())
    if invalid_row_count:
        suspicious_patterns.append(
            f"{invalid_row_count} malformed usage-log row(s) were skipped during analysis."
        )

    return {
        "log_paths": [str(path) for path in log_paths],
        "event_count": len(rows),
        "invalid_row_count": invalid_row_count,
        "invalid_rows_by_path": invalid_rows_by_path,
        "events_by_type": dict(events),
        "events_by_repo": dict(repos),
        "events_by_client": dict(clients),
        "session_count": len(sessions),
        "legacy_event_count": len(legacy_rows),
        "sessions": sessions,
        "suspicious_patterns": suspicious_patterns,
        "last_event": rows[-1] if rows else None,
    }


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

    rows, invalid_rows_by_path = normalize_rows(log_paths)
    summary = summarize_usage(rows, log_paths, invalid_rows_by_path)

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        return 0

    print("Usage log summary")
    print(f"- Total events: {summary['event_count']}")
    if summary["invalid_row_count"]:
        print(f"- Malformed rows skipped: {summary['invalid_row_count']}")
    print(f"- Sessions with ids: {summary['session_count']}")
    if summary["legacy_event_count"]:
        print(f"- Legacy events without session ids: {summary['legacy_event_count']}")
    print("- Events by type:")
    if summary["events_by_type"]:
        for event_type, count in summary["events_by_type"].items():
            print(f"  - {event_type}: {count}")
    else:
        print("  - none")
    print("- Events by client:")
    if summary["events_by_client"]:
        for client, count in summary["events_by_client"].items():
            print(f"  - {client}: {count}")
    else:
        print("  - none")
    print("- Session highlights:")
    if summary["sessions"]:
        for session in summary["sessions"]:
            published = ",".join(str(item) for item in session["published_release_numbers"]) or "none"
            print(
                f"  - {session['session_id']} ({session['repo']}): releases published [{published}], "
                f"events={sum(session['events_by_type'].values())}"
            )
            for pattern in session.get("suspicious_patterns", []):
                print(f"    suspicious: {pattern}")
    else:
        print("  - none")
    if summary["suspicious_patterns"]:
        print("- Suspicious patterns:")
        for pattern in summary["suspicious_patterns"]:
            print(f"  - {pattern}")
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
