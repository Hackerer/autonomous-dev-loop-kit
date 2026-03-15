#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import LoopError, find_repo_root, load_state, save_state, utc_now


def merge_unique(existing: list[str], new_values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*existing, *new_values]:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def update_council_slot(slot: dict, summary: str | None, decision: str | None, dissent: list[str]) -> dict:
    next_slot = dict(slot if isinstance(slot, dict) else {})
    if summary:
        next_slot["summary"] = summary
        next_slot["status"] = "captured"
    if decision:
        next_slot["decision"] = decision
        next_slot["status"] = "captured"
    next_slot["dissent"] = merge_unique(list(next_slot.get("dissent", [])), dissent)
    if next_slot["dissent"] and next_slot.get("status") == "not_started":
        next_slot["status"] = "captured"
    return next_slot


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist research and committee review conclusions for the current iteration.")
    parser.add_argument("--research", action="append", default=[], help="Research finding to persist.")
    parser.add_argument("--research-summary", help="Structured research-gate summary.")
    parser.add_argument("--evidence-ref", action="append", default=[], help="Research evidence reference to persist.")
    parser.add_argument("--quality-score", type=float, help="Structured research-gate quality score.")
    parser.add_argument("--open-gap", action="append", default=[], help="Open research gap to persist.")
    parser.add_argument("--committee-feedback", action="append", default=[], help="Committee feedback bullet to persist.")
    parser.add_argument("--decision", action="append", default=[], help="Committee decision bullet to persist.")
    parser.add_argument("--product-summary", help="Structured product council summary.")
    parser.add_argument("--product-decision", help="Structured product council decision.")
    parser.add_argument("--product-dissent", action="append", default=[], help="Product council dissent bullet.")
    parser.add_argument("--architecture-summary", help="Structured architecture council summary.")
    parser.add_argument("--architecture-decision", help="Structured architecture council decision.")
    parser.add_argument("--architecture-dissent", action="append", default=[], help="Architecture council dissent bullet.")
    parser.add_argument("--operator-summary", help="Structured operator council summary.")
    parser.add_argument("--operator-decision", help="Structured operator council decision.")
    parser.add_argument("--operator-dissent", action="append", default=[], help="Operator council dissent bullet.")
    parser.add_argument("--selected-goal", help="Structured selected goal for the scope decision.")
    parser.add_argument("--why-selected", help="Why this goal was selected now.")
    parser.add_argument("--scope-in", action="append", default=[], help="Structured scope-in bullet.")
    parser.add_argument("--scope-out", action="append", default=[], help="Structured scope-out bullet.")
    parser.add_argument("--assumption", action="append", default=[], help="Structured assumption bullet.")
    parser.add_argument("--risk", action="append", default=[], help="Structured risk bullet.")
    parser.add_argument("--required-validation", action="append", default=[], help="Required validation bullet.")
    parser.add_argument("--stop-condition", action="append", default=[], help="Structured stop-condition bullet.")
    parser.add_argument("--scope-dissent", action="append", default=[], help="Structured scope-decision dissent bullet.")
    parser.add_argument("--next-action", help="Next action after the scope decision.")
    parser.add_argument("--reflection", action="append", default=[], help="Optional reflection bullet to persist.")
    parser.add_argument("--json", action="store_true", help="Print the captured review payload as JSON.")
    parser.add_argument("--no-state", action="store_true", help="Validate and print the payload without updating state.")
    args = parser.parse_args()

    if (
        not args.research
        and not args.research_summary
        and not args.evidence_ref
        and args.quality_score is None
        and not args.open_gap
        and not args.committee_feedback
        and not args.decision
        and not args.product_summary
        and not args.product_decision
        and not args.product_dissent
        and not args.architecture_summary
        and not args.architecture_decision
        and not args.architecture_dissent
        and not args.operator_summary
        and not args.operator_decision
        and not args.operator_dissent
        and not args.selected_goal
        and not args.why_selected
        and not args.scope_in
        and not args.scope_out
        and not args.assumption
        and not args.risk
        and not args.required_validation
        and not args.stop_condition
        and not args.scope_dissent
        and not args.next_action
        and not args.reflection
    ):
        raise LoopError("At least one review input is required.")

    root = find_repo_root()
    state = load_state(root)
    goal = state.get("current_goal")
    existing = state.get("review_state", {})
    payload = dict(existing if isinstance(existing, dict) else {})
    payload["goal_id"] = goal.get("id") if isinstance(goal, dict) else payload.get("goal_id")
    payload["goal_title"] = goal.get("title") if isinstance(goal, dict) else payload.get("goal_title")
    payload["captured_at"] = utc_now()
    payload["research_findings"] = merge_unique(list(payload.get("research_findings", [])), list(args.research))
    payload["committee_feedback"] = merge_unique(list(payload.get("committee_feedback", [])), list(args.committee_feedback))
    payload["committee_decision"] = merge_unique(list(payload.get("committee_decision", [])), list(args.decision))
    payload["reflection_notes"] = merge_unique(list(payload.get("reflection_notes", [])), list(args.reflection))
    payload["status"] = "captured"

    research_gate = payload.get("research_gate", {})
    if not isinstance(research_gate, dict):
        research_gate = {}
    research_gate["status"] = "captured" if (
        args.research_summary or args.evidence_ref or args.quality_score is not None or args.open_gap
    ) else research_gate.get("status", "not_started")
    if args.research_summary:
        research_gate["summary"] = args.research_summary
    research_gate["evidence_refs"] = merge_unique(list(research_gate.get("evidence_refs", [])), list(args.evidence_ref))
    if args.quality_score is not None:
        research_gate["data_quality_score"] = args.quality_score
    research_gate["open_gaps"] = merge_unique(list(research_gate.get("open_gaps", [])), list(args.open_gap))
    payload["research_gate"] = research_gate
    councils = payload.get("councils", {})
    if not isinstance(councils, dict):
        councils = {}
    councils["product_council"] = update_council_slot(
        councils.get("product_council", {}),
        args.product_summary,
        args.product_decision,
        list(args.product_dissent),
    )
    councils["architecture_council"] = update_council_slot(
        councils.get("architecture_council", {}),
        args.architecture_summary,
        args.architecture_decision,
        list(args.architecture_dissent),
    )
    councils["operator_council"] = update_council_slot(
        councils.get("operator_council", {}),
        args.operator_summary,
        args.operator_decision,
        list(args.operator_dissent),
    )
    payload["councils"] = councils

    scope_decision = payload.get("scope_decision", {})
    if not isinstance(scope_decision, dict):
        scope_decision = {}
    has_scope_inputs = any(
        [
            args.selected_goal,
            args.why_selected,
            args.scope_in,
            args.scope_out,
            args.assumption,
            args.risk,
            args.required_validation,
            args.stop_condition,
            args.scope_dissent,
            args.next_action,
        ]
    )
    if has_scope_inputs:
        scope_decision["status"] = "captured"
    if args.selected_goal:
        scope_decision["selected_goal"] = args.selected_goal
    if args.why_selected:
        scope_decision["why_selected"] = args.why_selected
    scope_decision["scope_in"] = merge_unique(list(scope_decision.get("scope_in", [])), list(args.scope_in))
    scope_decision["scope_out"] = merge_unique(list(scope_decision.get("scope_out", [])), list(args.scope_out))
    scope_decision["assumptions"] = merge_unique(list(scope_decision.get("assumptions", [])), list(args.assumption))
    scope_decision["risks"] = merge_unique(list(scope_decision.get("risks", [])), list(args.risk))
    scope_decision["required_validation"] = merge_unique(
        list(scope_decision.get("required_validation", [])), list(args.required_validation)
    )
    scope_decision["stop_conditions"] = merge_unique(
        list(scope_decision.get("stop_conditions", [])), list(args.stop_condition)
    )
    scope_decision["dissent"] = merge_unique(list(scope_decision.get("dissent", [])), list(args.scope_dissent))
    if args.next_action:
        scope_decision["next_action"] = args.next_action
    payload["scope_decision"] = scope_decision

    if not args.no_state:
        state["review_state"] = payload
        state["status"] = "review_captured"
        save_state(root, state)

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print("Captured review state.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
