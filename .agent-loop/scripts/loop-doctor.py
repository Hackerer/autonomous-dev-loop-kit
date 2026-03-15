#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    find_repo_root,
    goal_title,
    implementation_gate_status,
    load_config,
    load_state,
    release_summary,
    review_state_matches_goal,
    session_summary,
    LoopError,
    git_remotes,
)


def diagnose(config: dict, state: dict, root) -> list[dict[str, str]]:
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
                "issue": "No autonomous release session is configured.",
                "next_step": "python3 .agent-loop/scripts/set-loop-session.py --iterations N",
            }
        )

    if config.get("planning", {}).get("release", {}).get("require_release_plan", True):
        if release["status"] in {"not_planned", "published"} and session["status"] == "active" and session["remaining_releases"] != 0:
            findings.append(
                {
                    "severity": "blocker",
                    "issue": "No active bundled release is planned for the current session.",
                    "next_step": "python3 .agent-loop/scripts/plan-release.py",
                }
            )

    if release["number"] is not None and release["remaining_goal_ids"] and not isinstance(goal, dict):
        findings.append(
            {
                "severity": "blocker",
                "issue": "The active release still has remaining goals but no active goal is selected.",
                "next_step": "python3 .agent-loop/scripts/select-next-goal.py",
            }
        )

    if isinstance(goal, dict):
        goal_id = str(goal.get("id", "")).strip()
        if not goal_id or goal_name == "unspecified goal":
            findings.append(
                {
                    "severity": "blocker",
                    "issue": "The active goal is missing or unspecified.",
                    "next_step": "python3 .agent-loop/scripts/select-next-goal.py",
                }
            )
        elif release["goal_ids"] and goal_id not in release["goal_ids"]:
            findings.append(
                {
                    "severity": "blocker",
                    "issue": "The active goal is not part of the active release.",
                    "next_step": "Re-select a goal from the active release or plan a new release intentionally.",
                }
            )

    if isinstance(goal, dict) and not review_state_matches_goal(review_state, goal):
        findings.append(
            {
                "severity": "blocker",
                "issue": "The recorded review state does not match the active goal.",
                "next_step": "python3 .agent-loop/scripts/capture-review.py ...",
            }
        )

    if gate["status"] in {"pending", "block"}:
        findings.append(
            {
                "severity": "blocker" if gate["status"] == "block" else "warning",
                "issue": f"Implementation gate is {gate['status']} ({gate['mode']}, evaluator {gate['evaluation_result']}).",
                "next_step": "python3 .agent-loop/scripts/render-evaluator-brief.py && python3 .agent-loop/scripts/assert-implementation-readiness.py",
            }
        )

    if validation.get("status") == "failed":
        findings.append(
            {
                "severity": "blocker",
                "issue": "The last full validation run failed.",
                "next_step": "Fix the failing checks, then rerun `python3 .agent-loop/scripts/run-full-validation.py`.",
            }
        )

    if release["status"] == "ready_to_release" and not state.get("draft_release_report"):
        findings.append(
            {
                "severity": "warning",
                "issue": "All release tasks are complete but the bundled release report is still missing.",
                "next_step": "python3 .agent-loop/scripts/write-release-report.py",
            }
        )

    if state.get("draft_report") and not state.get("draft_iteration"):
        findings.append(
            {
                "severity": "warning",
                "issue": "A draft task report exists without a draft iteration marker.",
                "next_step": "Re-run `python3 .agent-loop/scripts/write-report.py` before publishing.",
            }
        )

    remotes = git_remotes(root) if (root / ".git").exists() else {}
    git_config = config.get("git", {}) if isinstance(config.get("git"), dict) else {}
    strategy = str(git_config.get("strategy", "push-branch")).strip() or "push-branch"
    remote_name = str(git_config.get("remote", "origin")).strip() or "origin"
    if strategy in {"push-branch", "direct-push"}:
        if git_config.get("require_remote", True) and not remotes:
            findings.append(
                {
                    "severity": "warning",
                    "issue": "No Git remote is configured for this repo.",
                    "next_step": "Configure the correct project remote before attempting publish.",
                }
            )
        elif git_config.get("require_remote", True) and remote_name not in remotes:
            findings.append(
                {
                    "severity": "blocker",
                    "issue": f"The configured Git remote `{remote_name}` is missing.",
                    "next_step": "Update `.agent-loop/config.json` or add the expected remote before publishing.",
                }
            )
        else:
            remote_urls = remotes.get(remote_name, [])
            if not remote_urls:
                findings.append(
                    {
                        "severity": "blocker",
                        "issue": f"The configured Git remote `{remote_name}` has no resolved URLs.",
                        "next_step": "Reconfigure the expected remote before publishing.",
                    }
                )
            elif git_config.get("require_github_remote", True) and not any("github.com" in url for url in remote_urls):
                findings.append(
                    {
                        "severity": "blocker",
                        "issue": f"The configured Git remote `{remote_name}` does not point to GitHub.",
                        "next_step": "Point the configured remote at the correct project GitHub repository before publishing.",
                    }
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose common autonomous loop blockers and suggest the next recovery step.")
    parser.add_argument("--json", action="store_true", help="Print the doctor payload as JSON.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    findings = diagnose(config, state, root)
    status = "healthy" if not findings else "attention_needed"
    payload = {
        "repo_root": str(root),
        "status": status,
        "findings": findings,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    print("Loop doctor")
    print(f"- Status: {status}")
    if not findings:
        print("- No common blockers detected.")
        return 0
    for finding in findings:
        print(f"- [{finding['severity']}] {finding['issue']}")
        print(f"  Next: {finding['next_step']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
