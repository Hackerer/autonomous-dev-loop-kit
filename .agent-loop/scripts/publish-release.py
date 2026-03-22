#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import (
    append_usage_log,
    cli_info,
    current_branch,
    ensure_git_repo,
    git,
    git_remotes,
    experiment_config,
    load_config,
    load_state,
    remote_exists,
    release_summary,
    require_no_report_placeholders,
    require_green_validation,
    save_state,
    session_summary,
    slugify,
    utc_now,
    LoopError,
    default_state,
    resolve_execution_roots,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="在所有发布任务完成后提交并发布汇总发布报告。")
    parser.add_argument("--message", help="显式 Git 提交信息。")
    args = parser.parse_args()

    kit_root, _, workspace_root = resolve_execution_roots()
    ensure_git_repo(workspace_root)
    config = load_config(kit_root)
    state = load_state(workspace_root)
    release = release_summary(state)
    require_green_validation(state)

    if release["status"] in {"not_planned", "published"} or release["number"] is None:
        raise LoopError("没有可发布的活动发布。")
    if release["remaining_goal_ids"]:
        raise LoopError("当前发布仍有未完成目标。请先完成汇总任务迭代的发布。")

    report_path = state.get("draft_release_report")
    if not report_path:
        raise LoopError("没有汇总发布报告草稿。请先运行 `python3 .agent-loop/scripts/write-release-report.py`。")
    require_no_report_placeholders(workspace_root / report_path, "Bundled release report")
    for item in release.get("task_iterations", []):
        if not isinstance(item, dict):
            continue
        task_report = str(item.get("report", "")).strip()
        if task_report:
            require_no_report_placeholders(workspace_root / task_report, "Bundled task report")

    git_config = config.get("git", {})
    strategy = git_config.get("strategy", "push-branch")
    remote = git_config.get("remote", "origin")

    experiment_policy = experiment_config(config)
    metric_name = experiment_policy.get("metric_path", "review_state.evaluation.weighted_score")
    task_iterations = release.get("task_iterations", [])
    latest_task = task_iterations[-1] if isinstance(task_iterations, list) and task_iterations else {}
    release_metric_value = None
    if isinstance(latest_task, dict):
        release_metric_value = latest_task.get("candidate_metric_value")
        if release_metric_value is None:
            release_metric_value = latest_task.get("evaluation_weighted_score")

    remotes = {}
    if strategy in {"push-branch", "direct-push"}:
        remotes = git_remotes(workspace_root)
        if git_config.get("require_remote", True) and not remotes:
            raise LoopError("当前项目没有配置 Git 远程。")
        if git_config.get("require_remote", True) and not remote_exists(workspace_root, remote):
            raise LoopError(f"配置的 Git 远程 '{remote}' 不存在于当前项目中。")
        remote_urls = remotes.get(remote, [])
        if not remote_urls:
            raise LoopError(f"无法解析 Git 远程 '{remote}' 的 URL。")
        if git_config.get("require_github_remote", True) and not any("github.com" in url for url in remote_urls):
            raise LoopError(f"Git 远程 '{remote}' 未指向 GitHub（{', '.join(remote_urls)}）。")

    published_at = utc_now()
    release_record = {
        "number": int(release["number"]),
        "session_id": session_summary(state).get("id"),
        "title": release["title"],
        "summary": release["summary"],
        "goal_ids": release["goal_ids"],
        "goal_titles": release["goal_titles"],
        "task_iterations": release["task_iterations"],
        "report": report_path,
        "metric_name": metric_name,
        "candidate_metric_value": release_metric_value,
        "published_at": published_at,
    }
    state["release_history"].append(release_record)
    state["release"] = default_state()["release"]
    state["draft_release_report"] = None
    state["session"]["completed_releases"] = int(state.get("session", {}).get("completed_releases", 0) or 0) + 1
    state["status"] = "release_published"
    session = session_summary(state)
    if session["target_releases"] is not None and session["completed_releases"] >= int(session["target_releases"]):
        state["session"]["status"] = "completed"
        state["session"]["ended_at"] = published_at
        state["status"] = "session_completed"
    else:
        state["session"]["status"] = "active"
    save_state(workspace_root, state)

    append_usage_log(
        workspace_root,
        config,
        "release_published",
        {
            "release_number": release_record["number"],
            "title": release_record["title"],
            "report": report_path,
        },
        target_root=workspace_root,
    )
    if state.get("session", {}).get("status") == "completed":
        append_usage_log(
        workspace_root,
        config,
        "session_completed",
        {
            "session_id": state.get("session", {}).get("id"),
            "completed_releases": state.get("session", {}).get("completed_releases"),
            "target_releases": state.get("session", {}).get("target_releases"),
        },
        target_root=workspace_root,
    )

    add_result = git(workspace_root, "add", "-A")
    if add_result.returncode != 0:
        raise LoopError(add_result.stderr.strip() or "git add -A 失败")

    release_number = int(release["number"])
    commit_message = args.message or f"feat(release): r{release_number} {slugify(release['title'] or f'release-{release_number}')}"
    commit_result = git(workspace_root, "commit", "-m", commit_message)
    if commit_result.returncode != 0:
        raise LoopError(commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit 失败")

    sha_result = git(workspace_root, "rev-parse", "HEAD")
    if sha_result.returncode != 0:
        raise LoopError(sha_result.stderr.strip() or "提交后无法解析 HEAD")
    commit_sha = sha_result.stdout.strip()

    if strategy in {"push-branch", "direct-push"}:
        push_result = git(workspace_root, "push", "-u", remote, current_branch(workspace_root))
        if push_result.returncode != 0:
            raise LoopError(push_result.stderr.strip() or push_result.stdout.strip() or "git push 失败")

    cli_info(f"已发布汇总发布 R{release_number}，提交 {commit_sha}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
