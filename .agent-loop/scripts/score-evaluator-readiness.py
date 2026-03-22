#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import committee_config, load_config, load_json, resolve_execution_roots, LoopError


def parse_scores(score_args: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for raw_item in score_args:
        if "=" not in raw_item:
            raise LoopError(f"--score 值无效 '{raw_item}'。应为 criterion=value。")
        key, value = raw_item.split("=", 1)
        key = key.strip()
        if not key:
            raise LoopError(f"--score 值无效 '{raw_item}'。必须提供指标名称。")
        try:
            scores[key] = float(value)
        except ValueError as exc:
            raise LoopError(f"--score 值无效 '{raw_item}'。分数必须是数字。") from exc
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description="根据已提交的规约计算评审准备分数。")
    parser.add_argument("--score", action="append", default=[], help="指标分数，格式为 criterion=value。")
    parser.add_argument("--rubric", help="覆盖规约路径，默认使用配置的评审规约。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出计算结果。")
    args = parser.parse_args()

    if not args.score:
        raise LoopError("至少需要提供一组 --score criterion=value。")

    kit_root, _, _ = resolve_execution_roots()
    config = load_config(kit_root)
    evaluator = committee_config(config).get("evaluator", {})
    rubric_ref = args.rubric or (evaluator.get("rubric_ref", "") if isinstance(evaluator, dict) else "")
    if not str(rubric_ref).strip():
        raise LoopError("没有配置评审规约。")

    rubric = load_json(kit_root / str(rubric_ref))
    criteria = rubric.get("criteria", {})
    thresholds = rubric.get("thresholds", {})
    if not isinstance(criteria, dict) or not criteria:
        raise LoopError("规约条目缺失或无效。")
    if not isinstance(thresholds, dict):
        raise LoopError("规约阈值缺失或无效。")

    scores = parse_scores(list(args.score))
    unknown = [criterion for criterion in scores if criterion not in criteria]
    if unknown:
        raise LoopError(f"未知的规约指标：{', '.join(sorted(unknown))}")

    missing = [criterion for criterion in criteria if criterion not in scores]
    if missing:
        raise LoopError(f"缺少规约指标：{', '.join(missing)}")

    weighted_score = 0.0
    for criterion, details in criteria.items():
        if not isinstance(details, dict):
            raise LoopError(f"规约指标 '{criterion}' 无效。")
        weight = details.get("weight")
        if not isinstance(weight, (int, float)):
            raise LoopError(f"规约指标 '{criterion}' 缺少数字权重。")
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

    print(f"规约：{payload['rubric_version']}")
    print(f"加权分数：{weighted_score}")
    print(f"结果：{result}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
