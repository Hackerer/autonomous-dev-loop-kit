#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import (
    append_usage_log,
    LoopError,
    current_branch,
    ensure_git_repo,
    find_repo_root,
    git,
    git_remotes,
    goal_title,
    load_backlog,
    load_config,
    load_state,
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
    parser = argparse.ArgumentParser(description="Commit and publish a validated autonomous iteration.")
    parser.add_argument("--message", help="Explicit Git commit message.")
    args = parser.parse_args()

    root = find_repo_root()
    ensure_git_repo(root)
    config = load_config(root)
    state = load_state(root)
    backlog = load_backlog(root)
    require_green_validation(state)
    session = require_session_capacity(config, state)

    iteration = state.get("draft_iteration")
    report_path = state.get("draft_report")
    if not iteration or not report_path:
        raise LoopError("No draft report exists. Run write-report.py before publishing.")
    require_no_report_placeholders(root / report_path, "Task iteration report")

    goal = require_selected_goal({"current_goal": state.get("current_goal"), "draft_goal": state.get("draft_goal")})
    require_goal_in_active_release(config, state, goal)
    require_review_state(config, state, goal)
    require_evaluator_pass(config, state, goal)
    goal_label = goal_title(goal)
    goal_slug = slugify(goal_label)

    git_config = config.get("git", {})
    strategy = git_config.get("strategy", "push-branch")
    remote = git_config.get("remote", "origin")
    branch_prefix = git_config.get("branch_prefix", "auto-loop/v")

    remotes = {}
    if strategy in {"push-branch", "direct-push"}:
        remotes = git_remotes(root)
        if git_config.get("require_remote", True) and not remotes:
            raise LoopError(
                "No Git remote is configured for this project. Each project must publish to its own GitHub repo. Confirm the correct remote with the user before publishing."
            )
        if git_config.get("require_remote", True) and not remote_exists(root, remote):
            known = ", ".join(sorted(remotes)) or "none"
            raise LoopError(
                f"Configured Git remote '{remote}' is not present in this project. Known remotes: {known}. Confirm the correct project GitHub remote with the user before publishing."
            )
        remote_urls = remotes.get(remote, [])
        if not remote_urls:
            raise LoopError(
                f"Unable to resolve URLs for Git remote '{remote}'. Confirm the correct project GitHub remote with the user before publishing."
            )
        if git_config.get("require_github_remote", True) and not any("github.com" in url for url in remote_urls):
            joined_urls = ", ".join(remote_urls)
            raise LoopError(
                f"Git remote '{remote}' does not point to GitHub ({joined_urls}). Each project should publish to its own GitHub repo. Confirm with the user before publishing."
            )

    if strategy == "push-branch":
        branch_name = ensure_branch(root, f"{branch_prefix}{int(iteration):03d}-{goal_slug}")
    else:
        branch_name = current_branch(root)

    published_at = utc_now()
    next_completed = session["completed_iterations"] + 1
    target = session["target_releases"]
    goal_id = goal.get("id") if isinstance(goal, dict) else None
    release = release_summary(state)

    state["iteration"] = int(iteration)
    state["last_report"] = report_path
    state["status"] = "published"
    state["session"]["completed_iterations"] = next_completed
    state["session"]["status"] = "active"
    state["history"].append(
        {
            "iteration": int(iteration),
            "goal": goal_label,
            "goal_id": goal_id,
            "release_number": release.get("number"),
            "release_title": release.get("title"),
            "evaluation_result": state.get("review_state", {}).get("evaluation", {}).get("result"),
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

    save_state(root, state)
    save_backlog(root, backlog)

    append_usage_log(
        root,
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
    )

    add_result = git(root, "add", "-A")
    if add_result.returncode != 0:
        raise LoopError(add_result.stderr.strip() or "git add -A failed")

    commit_message = args.message or f"feat(loop): v{int(iteration)} {goal_slug}"
    commit_result = git(root, "commit", "-m", commit_message)
    if commit_result.returncode != 0:
        raise LoopError(commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed")

    sha_result = git(root, "rev-parse", "HEAD")
    if sha_result.returncode != 0:
        raise LoopError(sha_result.stderr.strip() or "Unable to resolve HEAD after commit")
    commit_sha = sha_result.stdout.strip()

    if strategy in {"push-branch", "direct-push"}:
        push_target = branch_name if strategy == "push-branch" else current_branch(root)
        push_result = git(root, "push", "-u", remote, push_target)
        if push_result.returncode != 0:
            raise LoopError(push_result.stderr.strip() or push_result.stdout.strip() or "git push failed")

    progress = session_summary(state)
    release_suffix = ""
    active = state.get("release", {})
    if isinstance(active, dict) and active.get("number") is not None:
        completed_goals = len(active.get("completed_goal_ids", [])) if isinstance(active.get("completed_goal_ids"), list) else 0
        total_goals = len(active.get("goal_ids", [])) if isinstance(active.get("goal_ids"), list) else 0
        release_suffix = f" (R{active.get('number')} tasks {completed_goals}/{total_goals})"
    if progress["target_releases"] is not None:
        print(
            f"Published iteration v{iteration} on {branch_name} at {commit_sha} "
            f"(session releases {progress['completed_releases']}/{progress['target_releases']}, "
            f"task iterations {progress['completed_iterations']}){release_suffix}"
        )
    else:
        print(f"Published iteration v{iteration} on {branch_name} at {commit_sha}{release_suffix}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
