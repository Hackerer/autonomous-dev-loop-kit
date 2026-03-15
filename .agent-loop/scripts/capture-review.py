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


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist research and committee review conclusions for the current iteration.")
    parser.add_argument("--research", action="append", default=[], help="Research finding to persist.")
    parser.add_argument("--research-summary", help="Structured research-gate summary.")
    parser.add_argument("--evidence-ref", action="append", default=[], help="Research evidence reference to persist.")
    parser.add_argument("--quality-score", type=float, help="Structured research-gate quality score.")
    parser.add_argument("--open-gap", action="append", default=[], help="Open research gap to persist.")
    parser.add_argument("--committee-feedback", action="append", default=[], help="Committee feedback bullet to persist.")
    parser.add_argument("--decision", action="append", default=[], help="Committee decision bullet to persist.")
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
