#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import LoopError, default_state, find_repo_root, load_state, save_state, utc_now


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


def parse_scores(score_args: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for raw_item in score_args:
        if "=" not in raw_item:
            raise LoopError(f"Invalid --score value '{raw_item}'. Expected criterion=value.")
        key, value = raw_item.split("=", 1)
        key = key.strip()
        if not key:
            raise LoopError(f"Invalid --score value '{raw_item}'. Criterion name is required.")
        try:
            scores[key] = float(value)
        except ValueError as exc:
            raise LoopError(f"Invalid --score value '{raw_item}'. Score must be numeric.") from exc
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist research and committee review conclusions for the current iteration.")
    parser.add_argument("--research", action="append", default=[], help="Research finding to persist.")
    parser.add_argument(
        "--research-status",
        choices=["not_started", "captured", "need_more_context"],
        help="Structured research-gate status.",
    )
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
    parser.add_argument("--rubric-version", help="Evaluator rubric version.")
    parser.add_argument("--score", action="append", default=[], help="Evaluator score in criterion=value form.")
    parser.add_argument("--weighted-score", type=float, help="Evaluator weighted score.")
    parser.add_argument("--evaluation-result", choices=["pass", "revise", "fail"], help="Evaluator final result.")
    parser.add_argument("--critique", action="append", default=[], help="Evaluator critique bullet.")
    parser.add_argument("--minimum-fix", action="append", default=[], help="Minimum fix required before implementation.")
    parser.add_argument(
        "--escalation-status",
        choices=["not_needed", "watch", "escalated"],
        help="Escalation status for the current iteration.",
    )
    parser.add_argument("--escalation-reason", help="Why the iteration should be watched or escalated.")
    parser.add_argument("--recommended-action", help="Recommended next action for the escalation.")
    parser.add_argument("--reflection", action="append", default=[], help="Optional reflection bullet to persist.")
    parser.add_argument("--json", action="store_true", help="Print the captured review payload as JSON.")
    parser.add_argument("--no-state", action="store_true", help="Validate and print the payload without updating state.")
    args = parser.parse_args()

    if (
        not args.research
        and not args.research_status
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
        and not args.rubric_version
        and not args.score
        and args.weighted_score is None
        and not args.evaluation_result
        and not args.critique
        and not args.minimum_fix
        and not args.escalation_status
        and not args.escalation_reason
        and not args.recommended_action
        and not args.reflection
    ):
        raise LoopError("At least one review input is required.")

    root = find_repo_root()
    state = load_state(root)
    goal = state.get("current_goal")
    existing = state.get("review_state", {})
    if not isinstance(existing, dict):
        existing = {}

    goal_id = goal.get("id") if isinstance(goal, dict) else None
    goal_title = goal.get("title") if isinstance(goal, dict) else None
    existing_goal_id = existing.get("goal_id")
    existing_goal_title = existing.get("goal_title")
    reset_for_new_goal = bool(goal) and (
        (goal_id and existing_goal_id and goal_id != existing_goal_id)
        or (goal_title and existing_goal_title and goal_title != existing_goal_title)
    )

    payload = dict(default_state()["review_state"] if reset_for_new_goal else existing)
    payload["goal_id"] = goal_id if goal_id is not None else payload.get("goal_id")
    payload["goal_title"] = goal_title if goal_title is not None else payload.get("goal_title")
    payload["captured_at"] = utc_now()
    payload["research_findings"] = merge_unique(list(payload.get("research_findings", [])), list(args.research))
    payload["committee_feedback"] = merge_unique(list(payload.get("committee_feedback", [])), list(args.committee_feedback))
    payload["committee_decision"] = merge_unique(list(payload.get("committee_decision", [])), list(args.decision))
    payload["reflection_notes"] = merge_unique(list(payload.get("reflection_notes", [])), list(args.reflection))
    payload["status"] = "captured"

    research_gate = payload.get("research_gate", {})
    if not isinstance(research_gate, dict):
        research_gate = {}
    if args.research_status:
        research_gate["status"] = args.research_status
    elif args.research_summary or args.evidence_ref or args.quality_score is not None or args.open_gap:
        research_gate["status"] = "captured"
    else:
        research_gate["status"] = research_gate.get("status", "not_started")
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

    evaluation = payload.get("evaluation", {})
    if not isinstance(evaluation, dict):
        evaluation = {}
    has_evaluation_inputs = any(
        [
            args.rubric_version,
            args.score,
            args.weighted_score is not None,
            args.evaluation_result,
            args.critique,
            args.minimum_fix,
        ]
    )
    if has_evaluation_inputs:
        evaluation["status"] = "captured"
    if args.rubric_version:
        evaluation["rubric_version"] = args.rubric_version
    if args.score:
        scores = dict(evaluation.get("scores", {}))
        scores.update(parse_scores(list(args.score)))
        evaluation["scores"] = scores
    if args.weighted_score is not None:
        evaluation["weighted_score"] = args.weighted_score
    if args.evaluation_result:
        evaluation["result"] = args.evaluation_result
    evaluation["critique"] = merge_unique(list(evaluation.get("critique", [])), list(args.critique))
    evaluation["minimum_fixes_required"] = merge_unique(
        list(evaluation.get("minimum_fixes_required", [])), list(args.minimum_fix)
    )
    payload["evaluation"] = evaluation

    escalation = payload.get("escalation", {})
    if not isinstance(escalation, dict):
        escalation = {}
    if args.escalation_status:
        escalation["status"] = args.escalation_status
    if args.escalation_reason:
        escalation["reason"] = args.escalation_reason
    if args.recommended_action:
        escalation["recommended_action"] = args.recommended_action
    payload["escalation"] = escalation

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
