#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    cli_info,
    goal_title,
    implementation_gate_status,
    experiment_status,
    load_config,
    load_state,
    release_summary,
    review_state_matches_goal,
    session_summary,
    resolve_execution_roots,
    LoopError,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="显示当前自治循环会话、发布和门禁状态。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出状态载荷。")
    args = parser.parse_args()

    kit_root, _, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    session = session_summary(state)
    release = release_summary(state)
    goal = state.get("current_goal") or state.get("draft_goal")
    review_state = state.get("review_state", {})
    review_matches = review_state_matches_goal(review_state, goal)
    evaluation = review_state.get("evaluation", {}) if isinstance(review_state, dict) else {}
    experiment = experiment_status(state)
    validation = state.get("last_validation", {})

    payload = {
        "repo_root": str(workspace_root),
        "state_status": state.get("status"),
        "session": session,
        "release": release,
        "goal": {
            "id": goal.get("id"),
            "title": goal_title(goal),
        }
        if isinstance(goal, dict)
        else None,
        "review": {
            "status": review_state.get("status") if isinstance(review_state, dict) else "not_started",
            "matches_active_goal": review_matches,
            "goal_id": review_state.get("goal_id") if isinstance(review_state, dict) else None,
            "goal_title": review_state.get("goal_title") if isinstance(review_state, dict) else None,
        },
        "implementation_gate": implementation_gate_status(config, evaluation if isinstance(evaluation, dict) else {}),
        "experiment": {
            "status": experiment.get("status"),
            "base_metric": experiment.get("base", {}).get("metric_value") if isinstance(experiment.get("base"), dict) else None,
            "candidate_metric": experiment.get("candidate", {}).get("metric_value") if isinstance(experiment.get("candidate"), dict) else None,
            "comparison_result": experiment.get("comparison", {}).get("result") if isinstance(experiment.get("comparison"), dict) else None,
            "promotion_decision": experiment.get("promotion", {}).get("decision") if isinstance(experiment.get("promotion"), dict) else None,
        },
        "validation": {
            "status": validation.get("status"),
            "ran_at": validation.get("ran_at"),
        }
        if isinstance(validation, dict)
        else {"status": "not_run", "ran_at": None},
        "drafts": {
            "draft_iteration": state.get("draft_iteration"),
            "draft_report": state.get("draft_report"),
            "draft_release_report": state.get("draft_release_report"),
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    cli_info("循环状态")
    print(f"- 状态：{payload['state_status']}")
    print(
        f"- 会话：{session['status']} "
        f"（{session['completed_releases']}/{session['target_releases']} 次发布，"
        f"{session['completed_iterations']} 次任务迭代）"
        if session["target_releases"] is not None
        else f"- 会话：{session['status']}"
    )
    if release["number"] is not None:
        print(
            f"- 当前发布：R{release['number']} {release['title']} "
            f"（已完成 {len(release['completed_goal_ids'])}/{len(release['goal_ids'])} 个任务）"
        )
    else:
        print("- 当前发布：无")
    print(f"- 当前目标：{goal_title(goal)}")
    print(f"- 评审状态：{payload['review']['status']}（匹配当前目标：{review_matches}）")
    gate = payload["implementation_gate"]
    print(f"- 实施门禁：{gate['status']}（{gate['mode']}，评审结果 {gate['evaluation_result']}）")
    experiment_payload = payload["experiment"]
    print(
        f"- 实验：{experiment_payload['status']}"
        + (
            f"（基线 {experiment_payload['base_metric']}，候选 {experiment_payload['candidate_metric']}，决策 {experiment_payload['promotion_decision'] or experiment_payload['comparison_result']}）"
            if experiment_payload["base_metric"] is not None or experiment_payload["candidate_metric"] is not None
            else ""
        )
    )
    validation_payload = payload["validation"]
    print(f"- 最近验证：{validation_payload['status']}，时间 {validation_payload['ran_at']}")
    drafts = payload["drafts"]
    print(f"- 任务报告草稿：{drafts['draft_report'] or '无'}")
    print(f"- 发布报告草稿：{drafts['draft_release_report'] or '无'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
