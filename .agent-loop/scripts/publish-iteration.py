#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import (
    append_usage_log,
    cli_info,
    LoopError,
    current_branch,
    ensure_git_repo,
    experiment_config,
    experiment_status,
    git,
    git_remotes,
    current_candidate_metric,
    goal_title,
    load_backlog,
    load_config,
    load_state,
    latest_promoted_metric_value,
    require_goal_in_active_release,
    require_session_capacity,
    require_selected_goal,
    remote_exists,
    require_evaluator_pass,
    require_green_validation,
    require_no_report_placeholders,
    require_review_state,
    release_summary,
    save_backlog,
    save_state,
    session_summary,
    slugify,
    utc_now,
    promote_candidate_decision,
    resolve_execution_roots,
)


def ensure_branch(root, branch_name: str) -> str:
    current = current_branch(root)
    if current == branch_name:
        return current

    probe = git(root, "rev-parse", "--verify", branch_name)
    if probe.returncode == 0:
        checkout = git(root, "checkout", branch_name)
    else:
        checkout = git(root, "checkout", "-b", branch_name)
    if checkout.returncode != 0:
        raise LoopError(checkout.stderr.strip() or f"Unable to checkout {branch_name}")
    return branch_name


def main() -> int:
    parser = argparse.ArgumentParser(description="提交并发布已验证通过的自治迭代。")
    parser.add_argument("--message", help="显式 Git 提交信息。")
    args = parser.parse_args()

    kit_root, target_root, workspace_root = resolve_execution_roots()
    ensure_git_repo(target_root)
    config = load_config(kit_root)
    state = load_state(workspace_root)
    backlog = load_backlog(workspace_root)
    require_green_validation(state)
    session = require_session_capacity(config, state)

    iteration = state.get("draft_iteration")
    report_path = state.get("draft_report")
    if not iteration or not report_path:
        raise LoopError("没有任务报告草稿。请先运行 write-report.py 再发布。")
    require_no_report_placeholders(workspace_root / report_path, "Task iteration report")

    goal = require_selected_goal({"current_goal": state.get("current_goal"), "draft_goal": state.get("draft_goal")})
    require_goal_in_active_release(config, state, goal)
    require_evaluator_pass(config, state, goal)
    review_state = require_review_state(config, state, goal)
    experiment_policy = experiment_config(config)
    if experiment_policy.get("enabled", True):
        promote, reason, baseline_value, candidate_value = promote_candidate_decision(
            state,
            allow_equal=bool(experiment_policy.get("allow_equal", False)),
        )
        if not promote:
            raise LoopError("候选版本尚未优于当前基线。" + (reason or "请继续迭代后再发布。"))
    goal_label = goal_title(goal)
    goal_slug = slugify(goal_label)

    git_config = config.get("git", {})
    strategy = git_config.get("strategy", "push-branch")
    remote = git_config.get("remote", "origin")
    branch_prefix = git_config.get("branch_prefix", "auto-loop/v")

    remotes = {}
    if strategy in {"push-branch", "direct-push"}:
        remotes = git_remotes(target_root)
        if git_config.get("require_remote", True) and not remotes:
            raise LoopError("当前项目没有配置 Git 远程。每个项目都应发布到自己的 GitHub 仓库。请在发布前与用户确认正确远程。")
        if git_config.get("require_remote", True) and not remote_exists(target_root, remote):
            known = ", ".join(sorted(remotes)) or "none"
            raise LoopError(f"配置的 Git 远程 '{remote}' 不存在于当前项目中。已知远程：{known}。请在发布前与用户确认正确的项目 GitHub 远程。")
        remote_urls = remotes.get(remote, [])
        if not remote_urls:
            raise LoopError(f"无法解析 Git 远程 '{remote}' 的 URL。请在发布前与用户确认正确的项目 GitHub 远程。")
        if git_config.get("require_github_remote", True) and not any("github.com" in url for url in remote_urls):
            joined_urls = ", ".join(remote_urls)
            raise LoopError(f"Git 远程 '{remote}' 未指向 GitHub（{joined_urls}）。每个项目都应发布到自己的 GitHub 仓库。请在发布前与用户确认。")

    if strategy == "push-branch":
        branch_name = ensure_branch(target_root, f"{branch_prefix}{int(iteration):03d}-{goal_slug}")
    else:
        branch_name = current_branch(target_root)

    published_at = utc_now()
    next_completed = session["completed_iterations"] + 1
    target = session["target_releases"]
    goal_id = goal.get("id") if isinstance(goal, dict) else None
    release = release_summary(state)
    candidate_metric = current_candidate_metric(state)
    baseline_metric = latest_promoted_metric_value(state)
    experiment = experiment_status(state)
    promotion = experiment.get("promotion", {}) if isinstance(experiment, dict) else {}
    comparison = experiment.get("comparison", {}) if isinstance(experiment, dict) else {}
    comparison_result = str(comparison.get("result", "")).strip() if isinstance(comparison, dict) else ""
    if comparison_result not in {"promote", "revise", "discard"}:
        comparison_result = "promote"

    state["iteration"] = int(iteration)
    state["last_report"] = report_path
    state["status"] = "published"
    state["session"]["completed_iterations"] = next_completed
    state["session"]["status"] = "active"
    state["history"].append(
        {
            "session_id": session.get("id"),
            "iteration": int(iteration),
            "goal": goal_label,
            "goal_id": goal_id,
            "release_number": release.get("number"),
            "release_title": release.get("title"),
            "evaluation_result": state.get("review_state", {}).get("evaluation", {}).get("result"),
            "evaluation_weighted_score": state.get("review_state", {}).get("evaluation", {}).get("weighted_score"),
            "candidate_metric_value": candidate_metric,
            "baseline_metric_value": baseline_metric,
            "experiment_decision": str(promotion.get("decision", comparison_result)).strip() or "promote",
            "validation_status": state.get("last_validation", {}).get("status"),
            "escalation_status": state.get("review_state", {}).get("escalation", {}).get("status"),
            "report": report_path,
            "branch": branch_name,
            "published_at": published_at,
            "session_progress": (
                None if target is None else f"{state['session'].get('completed_releases', 0)}/{int(target)} releases"
            ),
        }
    )
    if release.get("number") is not None and goal_id and goal_id in release.get("goal_ids", []):
        completed_goal_ids = [str(item) for item in state["release"].get("completed_goal_ids", []) if str(item).strip()]
        if goal_id not in completed_goal_ids:
            completed_goal_ids.append(goal_id)
        task_iterations = state["release"].get("task_iterations", [])
        if not isinstance(task_iterations, list):
            task_iterations = []
        task_iterations.append(
            {
                "iteration": int(iteration),
                "goal": goal_label,
                "goal_id": goal_id,
                "report": report_path,
                "candidate_metric_value": candidate_metric,
                "baseline_metric_value": baseline_metric,
                "experiment_decision": str(promotion.get("decision", comparison_result)).strip() or "promote",
                "published_at": published_at,
            }
        )
        state["release"]["completed_goal_ids"] = completed_goal_ids
        state["release"]["task_iterations"] = task_iterations
        state["release"]["status"] = (
            "ready_to_release"
            if len(completed_goal_ids) >= len(release.get("goal_ids", []))
            else "in_progress"
        )
    state["draft_iteration"] = None
    state["draft_report"] = None
    state["draft_goal"] = None
    state["current_goal"] = None

    if goal_id:
        for item in backlog:
            if item.get("id") == goal_id:
                item["status"] = "completed"
                break

    save_state(workspace_root, state)
    save_backlog(workspace_root, backlog)

    append_usage_log(
        workspace_root,
        config,
        "iteration_published",
        {
            "iteration": int(iteration),
            "goal": goal_label,
            "goal_id": goal_id or "",
            "release_number": release.get("number"),
            "report": report_path,
            "branch": branch_name,
        },
        target_root=target_root,
    )

    add_result = git(target_root, "add", "-A")
    if add_result.returncode != 0:
        raise LoopError(add_result.stderr.strip() or "git add -A 失败")

    commit_message = args.message or f"feat(loop): v{int(iteration)} {goal_slug}"
    commit_result = git(target_root, "commit", "-m", commit_message)
    if commit_result.returncode != 0:
        raise LoopError(commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit 失败")

    sha_result = git(target_root, "rev-parse", "HEAD")
    if sha_result.returncode != 0:
        raise LoopError(sha_result.stderr.strip() or "提交后无法解析 HEAD")
    commit_sha = sha_result.stdout.strip()

    if strategy in {"push-branch", "direct-push"}:
        push_target = branch_name if strategy == "push-branch" else current_branch(target_root)
        push_result = git(target_root, "push", "-u", remote, push_target)
        if push_result.returncode != 0:
            raise LoopError(push_result.stderr.strip() or push_result.stdout.strip() or "git push 失败")

    progress = session_summary(state)
    release_suffix = ""
    active = state.get("release", {})
    if isinstance(active, dict) and active.get("number") is not None:
        completed_goals = len(active.get("completed_goal_ids", [])) if isinstance(active.get("completed_goal_ids"), list) else 0
        total_goals = len(active.get("goal_ids", [])) if isinstance(active.get("goal_ids"), list) else 0
        release_suffix = f" (R{active.get('number')} tasks {completed_goals}/{total_goals})"
    if progress["target_releases"] is not None:
        cli_info(
            f"已发布迭代 v{iteration}，分支 {branch_name}，提交 {commit_sha} "
            f"（会话发布 {progress['completed_releases']}/{progress['target_releases']}，"
            f"任务迭代 {progress['completed_iterations']}）{release_suffix}"
        )
    else:
        cli_info(f"已发布迭代 v{iteration}，分支 {branch_name}，提交 {commit_sha}{release_suffix}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
