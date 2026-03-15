#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import (
    append_usage_log,
    current_branch,
    ensure_git_repo,
    find_repo_root,
    git,
    git_remotes,
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
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit and publish a bundled release report after all release tasks are shipped.")
    parser.add_argument("--message", help="Explicit Git commit message.")
    args = parser.parse_args()

    root = find_repo_root()
    ensure_git_repo(root)
    config = load_config(root)
    state = load_state(root)
    release = release_summary(state)
    require_green_validation(state)

    if release["status"] in {"not_planned", "published"} or release["number"] is None:
        raise LoopError("No active release exists to publish.")
    if release["remaining_goal_ids"]:
        raise LoopError("The active release still has incomplete goals. Finish publishing the bundled task iterations first.")

    report_path = state.get("draft_release_report")
    if not report_path:
        raise LoopError("No draft release report exists. Run `python3 .agent-loop/scripts/write-release-report.py` first.")
    require_no_report_placeholders(root / report_path, "Bundled release report")
    for item in release.get("task_iterations", []):
        if not isinstance(item, dict):
            continue
        task_report = str(item.get("report", "")).strip()
        if task_report:
            require_no_report_placeholders(root / task_report, "Bundled task report")

    git_config = config.get("git", {})
    strategy = git_config.get("strategy", "push-branch")
    remote = git_config.get("remote", "origin")

    add_result = git(root, "add", "-A")
    if add_result.returncode != 0:
        raise LoopError(add_result.stderr.strip() or "git add -A failed")

    release_number = int(release["number"])
    commit_message = args.message or f"feat(release): r{release_number} {slugify(release['title'] or f'release-{release_number}')}"
    commit_result = git(root, "commit", "-m", commit_message)
    if commit_result.returncode != 0:
        raise LoopError(commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed")

    sha_result = git(root, "rev-parse", "HEAD")
    if sha_result.returncode != 0:
        raise LoopError(sha_result.stderr.strip() or "Unable to resolve HEAD after commit")
    commit_sha = sha_result.stdout.strip()

    if strategy in {"push-branch", "direct-push"}:
        remotes = git_remotes(root)
        if git_config.get("require_remote", True) and not remotes:
            raise LoopError("No Git remote is configured for this project.")
        if git_config.get("require_remote", True) and not remote_exists(root, remote):
            raise LoopError(f"Configured Git remote '{remote}' is not present in this project.")
        remote_urls = remotes.get(remote, [])
        if not remote_urls:
            raise LoopError(f"Unable to resolve URLs for Git remote '{remote}'.")
        if git_config.get("require_github_remote", True) and not any("github.com" in url for url in remote_urls):
            raise LoopError(f"Git remote '{remote}' does not point to GitHub ({', '.join(remote_urls)}).")
        push_result = git(root, "push", "-u", remote, current_branch(root))
        if push_result.returncode != 0:
            raise LoopError(push_result.stderr.strip() or push_result.stdout.strip() or "git push failed")

    published_at = utc_now()
    state = load_state(root)
    release = release_summary(state)
    release_record = {
        "number": release_number,
        "session_id": session_summary(state).get("id"),
        "title": release["title"],
        "summary": release["summary"],
        "goal_ids": release["goal_ids"],
        "goal_titles": release["goal_titles"],
        "task_iterations": release["task_iterations"],
        "report": report_path,
        "published_at": published_at,
        "commit": commit_sha,
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
    save_state(root, state)

    append_usage_log(
        root,
        config,
        "release_published",
        {
            "release_number": release_number,
            "title": release_record["title"],
            "report": report_path,
            "commit": commit_sha,
        },
    )
    if state.get("session", {}).get("status") == "completed":
        append_usage_log(
            root,
            config,
            "session_completed",
            {
                "session_id": state.get("session", {}).get("id"),
                "completed_releases": state.get("session", {}).get("completed_releases"),
                "target_releases": state.get("session", {}).get("target_releases"),
            },
        )

    print(f"Published release R{release_number} at {commit_sha}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
