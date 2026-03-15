#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from common import (
    committee_summary,
    implementation_gate_status,
    LoopError,
    find_repo_root,
    goal_title,
    load_config,
    load_json,
    load_state,
    release_summary,
    relpath,
    reporting_path,
    require_evaluator_pass,
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


def prefixed_lines(prefix: str, values: list[str]) -> list[str]:
    return [f"{prefix}{value}" for value in values if value.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a task-iteration report for the next autonomous loop step.")
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
    release = release_summary(state)

    iteration = int(state.get("iteration", 0)) + 1
    report_path = reporting_path(root, config, iteration)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    goal = state.get("current_goal")
    goal_label = goal_title(goal)
    today = datetime.now().date().isoformat()
    project_data = state.get("project_data", {})
    review_state = require_review_state(config, state, goal)
    require_evaluator_pass(config, state, goal)
    review_research = list(review_state.get("research_findings", []))
    review_feedback = list(review_state.get("committee_feedback", []))
    review_decision = list(review_state.get("committee_decision", []))
    review_reflection = list(review_state.get("reflection_notes", []))
    research_gate = review_state.get("research_gate", {})
    councils = review_state.get("councils", {})
    secretariat = review_state.get("secretariat", {})
    scope_decision = review_state.get("scope_decision", {})
    evaluation = review_state.get("evaluation", {})

    research_lines = merge_unique(args.research, review_research)
    if isinstance(research_gate, dict):
        summary = str(research_gate.get("summary", "")).strip()
        if summary:
            research_lines = merge_unique(research_lines, [f"Research gate summary: {summary}"])
        open_gaps = research_gate.get("open_gaps", [])
        if isinstance(open_gaps, list):
            research_lines = merge_unique(research_lines, [f"Open gap: {item}" for item in open_gaps if str(item).strip()])
    committee_lines = []
    for role in committee_summary(config):
        members = ", ".join(role["members"]) if role["members"] else "no named members"
        committee_lines.append(f"{role['label']}: {role['responsibility']} Members: {members}")
    if isinstance(councils, dict):
        council_labels = {
            "product_council": "Product Council",
            "architecture_council": "Architecture Council",
            "operator_council": "Operator Council",
        }
        for key, label in council_labels.items():
            council = councils.get(key, {})
            if not isinstance(council, dict):
                continue
            summary = str(council.get("summary", "")).strip()
            decision = str(council.get("decision", "")).strip()
            dissent = council.get("dissent", [])
            if summary:
                committee_lines.append(f"{label} summary: {summary}")
            if decision:
                committee_lines.append(f"{label} decision: {decision}")
            if isinstance(dissent, list):
                committee_lines.extend([f"{label} dissent: {item}" for item in dissent if str(item).strip()])
    committee_lines.extend(merge_unique(args.committee_feedback, review_feedback))
    committee_lines.extend(merge_unique(args.committee_decision, review_decision))

    secretariat_lines: list[str] = []
    if isinstance(secretariat, dict):
        delivery = secretariat.get("delivery_secretary", {})
        if isinstance(delivery, dict):
            summary = str(delivery.get("summary", "")).strip()
            next_action = str(delivery.get("next_action", "")).strip()
            if summary:
                secretariat_lines.append(f"Delivery Secretary summary: {summary}")
            if next_action:
                secretariat_lines.append(f"Delivery Secretary next action: {next_action}")
        audit = secretariat.get("audit_secretary", {})
        if isinstance(audit, dict):
            summary = str(audit.get("summary", "")).strip()
            decision_record = str(audit.get("decision_record", "")).strip()
            if summary:
                secretariat_lines.append(f"Audit Secretary summary: {summary}")
            if decision_record:
                secretariat_lines.append(f"Audit decision record: {decision_record}")
            open_gaps = audit.get("open_gaps", [])
            if isinstance(open_gaps, list):
                secretariat_lines.extend(prefixed_lines("Audit open gap: ", [str(item) for item in open_gaps]))
            dissent_record = audit.get("dissent_record", [])
            if isinstance(dissent_record, list):
                secretariat_lines.extend(prefixed_lines("Audit dissent: ", [str(item) for item in dissent_record]))

    scope_lines: list[str] = []
    if isinstance(scope_decision, dict):
        why_selected = str(scope_decision.get("why_selected", "")).strip()
        if why_selected:
            scope_lines.append(f"Why selected: {why_selected}")
        if isinstance(scope_decision.get("scope_in"), list):
            scope_lines.extend(prefixed_lines("Scope in: ", [str(item) for item in scope_decision.get("scope_in", [])]))
        if isinstance(scope_decision.get("scope_out"), list):
            scope_lines.extend(prefixed_lines("Scope out: ", [str(item) for item in scope_decision.get("scope_out", [])]))
        if isinstance(scope_decision.get("assumptions"), list):
            scope_lines.extend(prefixed_lines("Assumption: ", [str(item) for item in scope_decision.get("assumptions", [])]))
        if isinstance(scope_decision.get("risks"), list):
            scope_lines.extend(prefixed_lines("Risk: ", [str(item) for item in scope_decision.get("risks", [])]))
        if isinstance(scope_decision.get("required_validation"), list):
            scope_lines.extend(
                prefixed_lines("Required validation: ", [str(item) for item in scope_decision.get("required_validation", [])])
            )
        if isinstance(scope_decision.get("stop_conditions"), list):
            scope_lines.extend(prefixed_lines("Stop condition: ", [str(item) for item in scope_decision.get("stop_conditions", [])]))
        if isinstance(scope_decision.get("dissent"), list):
            scope_lines.extend(prefixed_lines("Scope dissent: ", [str(item) for item in scope_decision.get("dissent", [])]))
        next_action = str(scope_decision.get("next_action", "")).strip()
        if next_action:
            scope_lines.append(f"Next action: {next_action}")

    evaluation_lines: list[str] = []
    if isinstance(evaluation, dict) and evaluation.get("status") == "captured":
        gate = implementation_gate_status(config, evaluation)
        evaluation_lines.append(
            f"Implementation gate: {gate.get('status')} ({gate.get('mode')}, evaluator {gate.get('evaluation_result')})"
        )
        rubric_version = str(evaluation.get("rubric_version", "")).strip()
        weighted_score = evaluation.get("weighted_score")
        result = str(evaluation.get("result", "")).strip()
        summary_bits = []
        if rubric_version:
            summary_bits.append(f"rubric `{rubric_version}`")
        if weighted_score is not None:
            summary_bits.append(f"weighted score `{weighted_score}`")
        if result:
            summary_bits.append(f"result `{result}`")
        if summary_bits:
            evaluation_lines.append("Evaluator outcome: " + ", ".join(summary_bits))
        scores = evaluation.get("scores", {})
        if isinstance(scores, dict):
            score_summary = ", ".join(f"{key}={value}" for key, value in scores.items())
            if score_summary:
                evaluation_lines.append(f"Evaluator scores: {score_summary}")
        critique = evaluation.get("critique", [])
        if isinstance(critique, list):
            evaluation_lines.extend(prefixed_lines("Evaluator critique: ", [str(item) for item in critique]))
        minimum_fixes = evaluation.get("minimum_fixes_required", [])
        if isinstance(minimum_fixes, list):
            evaluation_lines.extend(prefixed_lines("Minimum fix required: ", [str(item) for item in minimum_fixes]))

    stop_and_escalation_lines: list[str] = []
    if isinstance(research_gate, dict):
        open_gaps = research_gate.get("open_gaps", [])
        if isinstance(open_gaps, list):
            stop_and_escalation_lines.extend(prefixed_lines("Open gap: ", [str(item) for item in open_gaps]))
    if isinstance(scope_decision, dict):
        stop_conditions = scope_decision.get("stop_conditions", [])
        if isinstance(stop_conditions, list):
            stop_and_escalation_lines.extend(prefixed_lines("Stop condition: ", [str(item) for item in stop_conditions]))
    escalation = review_state.get("escalation", {})
    if isinstance(escalation, dict):
        status = str(escalation.get("status", "")).strip()
        reason = str(escalation.get("reason", "")).strip()
        recommended_action = str(escalation.get("recommended_action", "")).strip()
        if status:
            stop_and_escalation_lines.append(f"Escalation status: {status}")
        if reason:
            stop_and_escalation_lines.append(f"Escalation reason: {reason}")
        if recommended_action:
            stop_and_escalation_lines.append(f"Escalation action: {recommended_action}")

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
        f"# Task Iteration v{iteration} Report",
        "",
        f"Date: {today}",
        "",
        "## Session Progress",
        (
            f"- Release session progress: {session['completed_releases']}/{session['target_releases']}"
            if session["target_releases"] is not None
            else "- Release session progress: unbounded session"
        ),
        f"- Task iteration progress: {session['completed_iterations'] + 1}",
        (
            f"- Active release: R{release['number']} {release['title']}"
            if release["number"] is not None
            else "- Active release: no release planned"
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
        "## Secretariat",
        *bullet_lines(secretariat_lines, "Record the delivery and audit secretary outcome for this iteration."),
        "",
        "## Task Goal",
        f"- Goal: {goal_label}",
        *bullet_lines(args.acceptance, "Document the acceptance criteria for this task iteration."),
        "",
        "## Scope Decision",
        *bullet_lines(scope_lines, "Record why this goal was selected, what is in scope, what is out of scope, and where the stop line sits."),
        "",
        "## Key Observations",
        *bullet_lines(args.observation, "Capture the evidence or observation that most influenced this task iteration."),
        "",
        "## Evidence Sources",
        *bullet_lines(evidence_sources, "List the repo files, commands, or generated artifacts used for this task iteration."),
        "",
        "## Data Quality",
        *bullet_lines(quality_lines, "Record the latest project-data quality status or score."),
        "",
        "## Delivered",
        *bullet_lines(args.delivered, "List the concrete changes delivered in this task iteration."),
        "",
        "## Evaluation Readiness",
        *bullet_lines(evaluation_lines, "Record the evaluator outcome, weighted score, and minimum fixes when available."),
        "",
        "## Stop And Escalation",
        *bullet_lines(
            stop_and_escalation_lines,
            "Record open gaps, stop conditions, and escalation status so a later operator can see why the loop would stop or escalate.",
        ),
        "",
        "## Full Validation",
        *validation_lines,
        "",
        "## Reflection",
        *bullet_lines(merge_unique(args.reflection, review_reflection), "Reflect on requirement clarity and architectural impact."),
        "",
        "## Proposed Next Goal",
        *bullet_lines(args.next_goal, "Propose the next highest-value task inside the current release or the next release theme."),
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
