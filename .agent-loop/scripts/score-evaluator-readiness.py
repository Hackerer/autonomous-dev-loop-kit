#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import committee_config, find_repo_root, load_config, load_json, LoopError


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
    parser = argparse.ArgumentParser(description="Compute evaluator readiness score from the committed rubric.")
    parser.add_argument("--score", action="append", default=[], help="Criterion score in criterion=value form.")
    parser.add_argument("--rubric", help="Override rubric path. Defaults to the configured evaluator rubric.")
    parser.add_argument("--json", action="store_true", help="Print the computed score payload as JSON.")
    args = parser.parse_args()

    if not args.score:
        raise LoopError("At least one --score criterion=value pair is required.")

    root = find_repo_root()
    config = load_config(root)
    evaluator = committee_config(config).get("evaluator", {})
    rubric_ref = args.rubric or (evaluator.get("rubric_ref", "") if isinstance(evaluator, dict) else "")
    if not str(rubric_ref).strip():
        raise LoopError("No evaluator rubric is configured.")

    rubric = load_json(root / str(rubric_ref))
    criteria = rubric.get("criteria", {})
    thresholds = rubric.get("thresholds", {})
    if not isinstance(criteria, dict) or not criteria:
        raise LoopError("Rubric criteria are missing or invalid.")
    if not isinstance(thresholds, dict):
        raise LoopError("Rubric thresholds are missing or invalid.")

    scores = parse_scores(list(args.score))
    unknown = [criterion for criterion in scores if criterion not in criteria]
    if unknown:
        raise LoopError(f"Unknown rubric criteria: {', '.join(sorted(unknown))}")

    missing = [criterion for criterion in criteria if criterion not in scores]
    if missing:
        raise LoopError(f"Missing rubric criteria: {', '.join(missing)}")

    weighted_score = 0.0
    for criterion, details in criteria.items():
        if not isinstance(details, dict):
            raise LoopError(f"Rubric criterion '{criterion}' is invalid.")
        weight = details.get("weight")
        if not isinstance(weight, (int, float)):
            raise LoopError(f"Rubric criterion '{criterion}' is missing a numeric weight.")
        weighted_score += float(scores[criterion]) * float(weight)
    weighted_score = round(weighted_score, 2)

    pass_threshold = float(thresholds.get("pass", 4.0))
    revise_threshold = float(thresholds.get("revise", 3.0))
    if weighted_score >= pass_threshold:
        result = "pass"
    elif weighted_score >= revise_threshold:
        result = "revise"
    else:
        result = "fail"

    payload = {
        "rubric_version": str(rubric.get("id", "")),
        "scores": scores,
        "weighted_score": weighted_score,
        "result": result,
        "thresholds": thresholds,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    print(f"Rubric: {payload['rubric_version']}")
    print(f"Weighted score: {weighted_score}")
    print(f"Result: {result}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
