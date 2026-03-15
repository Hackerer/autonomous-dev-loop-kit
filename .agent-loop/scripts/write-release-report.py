#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from common import (
    LoopError,
    active_release,
    find_repo_root,
    load_config,
    load_state,
    relpath,
    release_reporting_path,
    release_summary,
    require_green_validation,
    save_state,
    session_summary,
)


def section_map(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("## "):
            current = raw_line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(raw_line)
    return sections


def bulletize(lines: list[str], fallback: str) -> list[str]:
    values = [line for line in lines if line.strip()]
    if not values:
        return [f"- {fallback}"]
    bullets: list[str] = []
    for line in values:
        if line.startswith("- "):
            bullets.append(line)
        else:
            bullets.append(f"- {line}")
    return bullets


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a bundled release report that aggregates multiple task iterations.")
    parser.add_argument("--summary", action="append", default=[], help="Release-level summary bullet.")
    parser.add_argument("--output-note", action="append", default=[], help="Detailed output bullet for the release.")
    parser.add_argument("--next-release", action="append", default=[], help="Next-release recommendation bullet.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    release = release_summary(state)
    require_green_validation(state)

    if release["status"] in {"not_planned", "published"} or release["number"] is None:
        raise LoopError("No active release exists. Plan one first with `python3 .agent-loop/scripts/plan-release.py`.")
    if release["remaining_goal_ids"]:
        raise LoopError(
            "The active release still has incomplete goals. Finish and publish each task iteration before writing the release report."
        )

    release_number = int(release["number"])
    report_path = release_reporting_path(root, config, release_number)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().date().isoformat()
    session = session_summary(state)

    task_iterations = []
    for item in release.get("task_iterations", []):
        if isinstance(item, dict):
            task_iterations.append(item)

    delivered_lines: list[str] = []
    validation_lines: list[str] = []
    output_lines: list[str] = list(args.output_note)
    task_trace_lines: list[str] = []
    for item in task_iterations:
        task_label = f"v{item.get('iteration')} {item.get('goal', '')}".strip()
        report_rel = str(item.get("report", "")).strip()
        task_trace_lines.append(f"- {task_label} -> `{report_rel}`")
        if report_rel:
            sections = section_map(root / report_rel)
            delivered_lines.extend([f"{task_label}: {line[2:]}" for line in sections.get("Delivered", []) if line.startswith("- ")])
            validation_lines.extend([f"{task_label}: {line[2:]}" for line in sections.get("Full Validation", []) if line.startswith("- ")])
            output_lines.extend([f"{task_label}: {line[2:]}" for line in sections.get("Key Observations", []) if line.startswith("- ")])

    content = [
        f"# R{release_number} Release Report",
        "",
        f"Date: {today}",
        "",
        "## Release Definition",
        f"- Release: R{release_number}",
        f"- Title: {release['title'] or f'Release {release_number}'}",
        *bulletize(args.summary or [release["summary"]], "Document why this bundled release exists and what user-facing package it represents."),
        "",
        "## Included Scope",
        *bulletize(release["goal_titles"], "List the bundled goals included in this release."),
        "",
        "## Requirement Delivery",
        *bulletize(delivered_lines, "Summarize what this release delivered across the included task iterations."),
        "",
        "## Technical Validation",
        *bulletize(validation_lines, "Record the validation results that prove this release is technically sound."),
        "",
        "## Detailed Output",
        *bulletize(output_lines, "Explain the notable outputs, operator-visible behavior, and architectural consequences of this release."),
        "",
        "## Task Traceability",
        *bulletize(task_trace_lines, "Link each task iteration report that was bundled into this release."),
        "",
        "## Session Progress",
        (
            f"- Releases completed after publish: {session['completed_releases'] + 1}/{session['target_releases']}"
            if session["target_releases"] is not None
            else "- Releases completed after publish: unbounded session"
        ),
        f"- Task iterations included: {len(task_iterations)}",
        "",
        "## Next Release Recommendation",
        *bulletize(args.next_release, "Document the next bundled release theme or reason to stop."),
        "",
    ]

    report_path.write_text("\n".join(content), encoding="utf-8")
    state["draft_release_report"] = relpath(report_path, root)
    state["status"] = "release_report_written"
    save_state(root, state)
    print(report_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
