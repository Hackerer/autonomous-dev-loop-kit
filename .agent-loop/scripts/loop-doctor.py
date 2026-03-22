#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    cli_info,
    goal_title,
    implementation_gate_status,
    load_config,
    load_state,
    release_summary,
    review_state_matches_goal,
    session_summary,
    resolve_execution_roots,
    LoopError,
    git_remotes,
)


def diagnose(config: dict, state: dict, workspace_root, target_root) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    session = session_summary(state)
    release = release_summary(state)
    goal = state.get("current_goal") or state.get("draft_goal")
    goal_name = goal_title(goal)
    review_state = state.get("review_state", {}) if isinstance(state.get("review_state"), dict) else {}
    validation = state.get("last_validation", {}) if isinstance(state.get("last_validation"), dict) else {}
    gate = implementation_gate_status(config, review_state.get("evaluation", {}) if isinstance(review_state.get("evaluation"), dict) else {})

    if session["status"] == "not_configured":
        findings.append(
                {
                    "severity": "blocker",
                    "issue": "尚未配置自治发布会话。",
                    "next_step": "python3 .agent-loop/scripts/set-loop-session.py --iterations N",
                }
            )

    if config.get("planning", {}).get("release", {}).get("require_release_plan", True):
        if release["status"] in {"not_planned", "published"} and session["status"] == "active" and session["remaining_releases"] != 0:
            findings.append(
                {
                    "severity": "blocker",
                    "issue": "当前会话还没有活动的发布计划。",
                    "next_step": "python3 .agent-loop/scripts/plan-release.py",
                }
            )

    if release["number"] is not None and release["remaining_goal_ids"] and not isinstance(goal, dict):
        findings.append(
                {
                    "severity": "blocker",
                    "issue": "当前发布仍有未完成目标，但还没有选中活动目标。",
                    "next_step": "python3 .agent-loop/scripts/select-next-goal.py",
                }
            )

    if isinstance(goal, dict):
        goal_id = str(goal.get("id", "")).strip()
        if not goal_id or goal_name == "unspecified goal":
            findings.append(
                {
                    "severity": "blocker",
                    "issue": "当前目标缺失或未指定。",
                    "next_step": "python3 .agent-loop/scripts/select-next-goal.py",
                }
            )
        elif release["goal_ids"] and goal_id not in release["goal_ids"]:
            findings.append(
                {
                    "severity": "blocker",
                    "issue": "当前目标不属于活动发布。",
                    "next_step": "请从当前发布中重新选择目标，或有意规划一个新发布。",
                }
            )

    if isinstance(goal, dict) and not review_state_matches_goal(review_state, goal):
        findings.append(
                {
                    "severity": "blocker",
                    "issue": "已记录的评审状态与当前目标不匹配。",
                    "next_step": "python3 .agent-loop/scripts/capture-review.py ...",
                }
            )

    if gate["status"] in {"pending", "block"}:
        findings.append(
                {
                    "severity": "blocker" if gate["status"] == "block" else "warning",
                    "issue": f"实施门禁状态为 {gate['status']}（{gate['mode']}，评审结果 {gate['evaluation_result']}）。",
                    "next_step": "python3 .agent-loop/scripts/render-evaluator-brief.py && python3 .agent-loop/scripts/assert-implementation-readiness.py",
                }
            )

    if validation.get("status") == "failed":
        findings.append(
                {
                    "severity": "blocker",
                    "issue": "最近一次全量验证失败。",
                    "next_step": "Fix the failing checks, then rerun `python3 .agent-loop/scripts/run-full-validation.py`.",
                }
            )

    if release["status"] == "ready_to_release" and not state.get("draft_release_report"):
        findings.append(
                {
                    "severity": "warning",
                    "issue": "所有发布任务都已完成，但汇总发布报告仍然缺失。",
                    "next_step": "python3 .agent-loop/scripts/write-release-report.py",
                }
            )

    if state.get("draft_report") and not state.get("draft_iteration"):
        findings.append(
                {
                    "severity": "warning",
                    "issue": "存在任务报告草稿，但没有对应的草稿迭代标记。",
                    "next_step": "Re-run `python3 .agent-loop/scripts/write-report.py` before publishing.",
                }
            )

    remotes = git_remotes(target_root) if (target_root / ".git").exists() else {}
    git_config = config.get("git", {}) if isinstance(config.get("git"), dict) else {}
    strategy = str(git_config.get("strategy", "push-branch")).strip() or "push-branch"
    remote_name = str(git_config.get("remote", "origin")).strip() or "origin"
    if strategy in {"push-branch", "direct-push"}:
        if git_config.get("require_remote", True) and not remotes:
            findings.append(
                {
                    "severity": "warning",
                    "issue": "当前仓库没有配置 Git 远程。",
                    "next_step": "在尝试发布前，请先配置正确的项目远程。",
                }
            )
        elif git_config.get("require_remote", True) and remote_name not in remotes:
            findings.append(
                {
                    "severity": "blocker",
                    "issue": f"配置的 Git 远程 `{remote_name}` 不存在。",
                    "next_step": "请更新 `.agent-loop/config.json` 或在发布前添加预期远程。",
                }
            )
        else:
            remote_urls = remotes.get(remote_name, [])
            if not remote_urls:
                findings.append(
                {
                    "severity": "blocker",
                    "issue": f"配置的 Git 远程 `{remote_name}` 没有解析出的 URL。",
                    "next_step": "请在发布前重新配置预期远程。",
                }
            )
            elif git_config.get("require_github_remote", True) and not any("github.com" in url for url in remote_urls):
                findings.append(
                {
                    "severity": "blocker",
                    "issue": f"配置的 Git 远程 `{remote_name}` 并未指向 GitHub。",
                    "next_step": "请在发布前把该远程指向正确的项目 GitHub 仓库。",
                }
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="诊断自治循环中的常见阻塞，并给出下一步恢复动作。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出诊断载荷。")
    args = parser.parse_args()

    kit_root, target_root, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    findings = diagnose(config, state, workspace_root, target_root)
    status = "healthy" if not findings else "attention_needed"
    payload = {
        "kit_root": str(workspace_root),
        "target_root": str(target_root),
        "status": status,
        "findings": findings,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    cli_info("循环诊断")
    print(f"- 状态：{status}")
    if not findings:
        print("- 未发现常见阻塞。")
        return 0
    for finding in findings:
        print(f"- [{finding['severity']}] {finding['issue']}")
        print(f"  下一步：{finding['next_step']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
