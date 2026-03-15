#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from common import (
    committee_summary,
    LoopError,
    find_repo_root,
    goal_title,
    load_config,
    load_json,
    load_state,
    relpath,
    reporting_path,
    require_green_validation,
    require_review_state,
    save_state,
    session_summary,
)


def bullet_lines(values: list[str], fallback: str) -> list[str]:
    if not values:
        return [f"- {fallback}"]
    return [f"- {value}" for value in values]


def merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*primary, *secondary]:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a version report for the next autonomous iteration.")
    parser.add_argument("--analysis", action="append", default=[], help="Current-state analysis bullet.")
    parser.add_argument("--research", action="append", default=[], help="Research bullet gathered before goal selection.")
    parser.add_argument("--acceptance", action="append", default=[], help="Acceptance bullet for this version.")
    parser.add_argument("--committee-feedback", action="append", default=[], help="Committee feedback bullet.")
    parser.add_argument("--committee-decision", action="append", default=[], help="Committee decision bullet.")
    parser.add_argument("--observation", action="append", default=[], help="Key observation bullet from the ReAct cycle.")
    parser.add_argument("--source", action="append", default=[], help="Evidence source bullet for this version.")
    parser.add_argument("--quality-note", action="append", default=[], help="Data-quality bullet for this version.")
    parser.add_argument("--delivered", action="append", default=[], help="Delivered change bullet.")
    parser.add_argument("--reflection", action="append", default=[], help="Reflection bullet.")
    parser.add_argument("--next-goal", action="append", default=[], help="Next-goal proposal bullet.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    validation = require_green_validation(state)
    session = session_summary(state)

    iteration = int(state.get("iteration", 0)) + 1
    report_path = reporting_path(root, config, iteration)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    goal = state.get("current_goal")
    goal_label = goal_title(goal)
    today = datetime.now().date().isoformat()
    project_data = state.get("project_data", {})
    review_state = require_review_state(config, state, goal)
    review_research = list(review_state.get("research_findings", []))
    review_feedback = list(review_state.get("committee_feedback", []))
    review_decision = list(review_state.get("committee_decision", []))
    review_reflection = list(review_state.get("reflection_notes", []))

    research_lines = merge_unique(args.research, review_research)
    committee_lines = []
    for role in committee_summary(config):
        members = ", ".join(role["members"]) if role["members"] else "no named members"
        committee_lines.append(f"{role['label']}: {role['responsibility']} Members: {members}")
    committee_lines.extend(merge_unique(args.committee_feedback, review_feedback))
    committee_lines.extend(merge_unique(args.committee_decision, review_decision))

    validation_lines = []
    for result in validation.get("results", []):
        status = "PASS" if result.get("passed") else "FAIL"
        validation_lines.append(f"- `{result.get('command')}` -> {status} (exit {result.get('exit_code')})")
    if not validation_lines:
        validation_lines = ["- No validation results were recorded."]

    evidence_sources = list(args.source)
    snapshot_path = project_data.get("snapshot_path")
    quality_path = project_data.get("quality_path")
    if review_state:
        evidence_sources.append("Durable review state: `.agent-loop/state.json`")
    if snapshot_path:
        evidence_sources.append(f"Project data snapshot: `{snapshot_path}`")
    if quality_path:
        evidence_sources.append(f"Project data quality: `{quality_path}`")
    evidence_sources = merge_unique(evidence_sources, [])

    quality_lines = list(args.quality_note)
    if quality_path:
        quality_report = load_json(root / quality_path)
        quality_lines.append(
            f"Latest quality status: `{quality_report.get('status')}`, score `{quality_report.get('overall_score')}`"
        )
        gaps = quality_report.get("blocking_gaps", [])
        if gaps:
            quality_lines.append(f"Blocking gaps: {', '.join(gaps)}")

    content = [
        f"# v{iteration} Report",
        "",
        f"Date: {today}",
        "",
        "## Session Progress",
        (
            f"- Session progress: {session['completed_iterations'] + 1}/{session['target_iterations']}"
            if session["target_iterations"] is not None
            else "- Session progress: unbounded session"
        ),
        "",
        "## Current State Analysis",
        *bullet_lines(args.analysis, "Summarize the current repo state before this version."),
        "",
        "## Research",
        *bullet_lines(research_lines, "Summarize the repo, product, user, and architecture research completed before selecting this version."),
        "",
        "## Committee Review",
        *bullet_lines(committee_lines, "Record the requirement and review feedback from the product, architecture, and user committee."),
        "",
        "## Version Goal",
        f"- Goal: {goal_label}",
        *bullet_lines(args.acceptance, "Document the acceptance criteria for this version."),
        "",
        "## Key Observations",
        *bullet_lines(args.observation, "Capture the evidence or observation that most influenced this version."),
        "",
        "## Evidence Sources",
        *bullet_lines(evidence_sources, "List the repo files, commands, or generated artifacts used for this version."),
        "",
        "## Data Quality",
        *bullet_lines(quality_lines, "Record the latest project-data quality status or score."),
        "",
        "## Delivered",
        *bullet_lines(args.delivered, "List the concrete changes delivered in this version."),
        "",
        "## Full Validation",
        *validation_lines,
        "",
        "## Reflection",
        *bullet_lines(merge_unique(args.reflection, review_reflection), "Reflect on requirement clarity and architectural impact."),
        "",
        "## Proposed Next Goal",
        *bullet_lines(args.next_goal, "Propose the next highest-value small version."),
        "",
    ]
    report_path.write_text("\n".join(content), encoding="utf-8")

    state = load_state(root)
    state["draft_iteration"] = iteration
    state["draft_report"] = relpath(report_path, root)
    state["draft_goal"] = goal
    state["status"] = "report_written"
    save_state(root, state)

    print(report_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
