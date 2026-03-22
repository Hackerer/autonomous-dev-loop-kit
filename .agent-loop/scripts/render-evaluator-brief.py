#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    cli_info,
    implementation_gate_status,
    LoopError,
    committee_config,
    evaluator_summary,
    goal_title,
    load_config,
    load_json,
    load_state,
    require_review_state,
    resolve_execution_roots,
)


def build_project_context(root, state: dict) -> dict:
    project_data = state.get("project_data", {})
    snapshot_path = project_data.get("snapshot_path")
    snapshot = {}
    if snapshot_path:
        snapshot_file = root / snapshot_path
        if snapshot_file.exists():
            snapshot = load_json(snapshot_file, default={})

    repo = snapshot.get("repo", {}) if isinstance(snapshot, dict) else {}
    product_context = snapshot.get("product_context", {}) if isinstance(snapshot, dict) else {}
    validation = snapshot.get("validation", {}) if isinstance(snapshot, dict) else {}

    return {
        "target_outcome": str(product_context.get("target_outcome", "")),
        "constraints": list(product_context.get("constraints", [])) if isinstance(product_context.get("constraints"), list) else [],
        "current_branch": str(repo.get("current_branch", "")),
        "quality_status": project_data.get("last_quality_status"),
        "validation_commands": list(validation.get("configured_commands", []))
        if isinstance(validation.get("configured_commands"), list)
        else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="输出当前目标的独立评审器简报。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出评审器简报。")
    args = parser.parse_args()

    kit_root, _, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    goal = state.get("current_goal")
    if not goal:
        raise LoopError("尚未选择活动目标。请先运行 `python3 .agent-loop/scripts/select-next-goal.py`。")

    review_state = require_review_state(config, state, goal)
    scope_decision = review_state.get("scope_decision", {})
    if not isinstance(scope_decision, dict) or scope_decision.get("status") != "captured":
        raise LoopError(
            "当前目标缺少范围决策。请先运行 `python3 .agent-loop/scripts/capture-review.py ... --selected-goal ...` 再输出评审器简报。"
        )

    committee = committee_config(config)
    evaluator = committee.get("evaluator", {})
    rubric_ref = str(evaluator.get("rubric_ref", "")).strip() if isinstance(evaluator, dict) else ""
    if not rubric_ref:
        raise LoopError("未在 .agent-loop/config.json 中配置评审规约。")

    rubric = load_json(kit_root / rubric_ref)
    payload = {
        "goal": {
            "id": goal.get("id"),
            "title": goal_title(goal),
        },
        "scope_decision": {
            "selected_goal": scope_decision.get("selected_goal", ""),
            "why_selected": scope_decision.get("why_selected", ""),
            "scope_in": list(scope_decision.get("scope_in", [])),
            "scope_out": list(scope_decision.get("scope_out", [])),
            "assumptions": list(scope_decision.get("assumptions", [])),
            "risks": list(scope_decision.get("risks", [])),
            "required_validation": list(scope_decision.get("required_validation", [])),
            "stop_conditions": list(scope_decision.get("stop_conditions", [])),
        },
        "project_context": build_project_context(workspace_root, state),
        "evaluator": evaluator_summary(config),
        "implementation_gate": implementation_gate_status(config, review_state.get("evaluation", {})),
        "rubric": rubric,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    persona = payload["evaluator"].get("persona", {})
    cli_info("独立评审器简报")
    print(f"- 目标：{payload['goal']['title']}")
    print(f"- 评审器：{persona.get('label', '未配置评审器')}")
    print(f"- 规约：{rubric_ref}")
    print(
        f"- 实施门禁：{payload['implementation_gate'].get('status')} "
        f"（{payload['implementation_gate'].get('mode')}，评审结果 {payload['implementation_gate'].get('evaluation_result')}）"
    )
    print(f"- 目标结果：{payload['project_context'].get('target_outcome', '') or '未记录'}")
    print(f"- 当前分支：{payload['project_context'].get('current_branch', '') or '未知'}")
    print("- 范围内：")
    for item in payload["scope_decision"]["scope_in"] or ["未记录范围内项。"]:
        print(f"  - {item}")
    print("- 范围外：")
    for item in payload["scope_decision"]["scope_out"] or ["未记录范围外项。"]:
        print(f"  - {item}")
    print("- 必需验证：")
    for item in payload["scope_decision"]["required_validation"] or ["未记录必需验证。"]:
        print(f"  - {item}")
    print("- 规约条目：")
    for criterion, details in payload["rubric"].get("criteria", {}).items():
        question = details.get("question", "")
        weight = details.get("weight", "")
        print(f"  - {criterion} ({weight}): {question}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
