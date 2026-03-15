#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import find_repo_root, load_json, save_json, load_state, save_state, relpath

DEFAULT_REQUIRED_SIGNALS = [
    "collection_timestamp",
    "repo_root",
    "git_branch",
    "git_remote",
    "worktree_clean",
    "languages",
    "tooling_signals",
    "validation_commands",
    "target_outcome",
    "constraints",
    "direct_evidence",
]


def has_tooling_signals(project: dict) -> bool:
    return bool(
        project.get("package_managers")
        or project.get("runtime_files")
        or project.get("framework_signals")
        or project.get("tooling_signals")
        or project.get("repo_archetype")
    )


def profile_summary(snapshot: dict) -> dict:
    project = snapshot.get("project", {})
    if not isinstance(project, dict):
        project = {}
    profile = project.get("archetype_profile", {})
    if not isinstance(profile, dict):
        profile = {}
    required_signals = profile.get("required_signals", [])
    if not isinstance(required_signals, list) or not required_signals:
        required_signals = list(DEFAULT_REQUIRED_SIGNALS)
    return {
        "id": str(profile.get("id", "") or "baseline"),
        "label": str(profile.get("label", "") or "Baseline Repo"),
        "required_signals": [str(item) for item in required_signals if str(item).strip()],
        "committee_emphasis": [str(item) for item in profile.get("committee_emphasis", []) if str(item).strip()]
        if isinstance(profile.get("committee_emphasis"), list)
        else [],
    }


def signal_checks(snapshot: dict) -> dict[str, tuple[bool, str]]:
    repo = snapshot.get("repo", {})
    project = snapshot.get("project", {})
    validation = snapshot.get("validation", {})
    product_context = snapshot.get("product_context", {})
    evidence = snapshot.get("evidence", {})
    return {
        "collection_timestamp": (bool(snapshot.get("collected_at")), "missing collection timestamp"),
        "repo_root": (bool(repo.get("root")), "missing repo root"),
        "git_branch": (bool(repo.get("current_branch")), "missing current branch"),
        "git_remote": (bool(repo.get("remotes")), "missing git remotes"),
        "worktree_clean": (repo.get("worktree_clean") is not None, "missing worktree cleanliness signal"),
        "languages": (bool(project.get("languages")), "missing language detection"),
        "tooling_signals": (has_tooling_signals(project), "missing tooling or automation signals"),
        "repo_archetype": (bool(project.get("repo_archetype")), "missing repo archetype detection"),
        "validation_commands": (bool(validation.get("configured_commands")), "missing validation commands"),
        "target_outcome": (bool(product_context.get("target_outcome")), "missing target outcome"),
        "constraints": (bool(product_context.get("constraints")), "missing constraints"),
        "direct_evidence": (evidence.get("confidence") in {"direct", "derived"}, "low confidence evidence"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score whether collected project data is good enough to act on.")
    parser.add_argument("--input", help="Input project data JSON path.")
    parser.add_argument("--output", help="Output data quality JSON path.")
    parser.add_argument("--no-state", action="store_true", help="Do not persist quality metadata into .agent-loop/state.json.")
    args = parser.parse_args()

    root = find_repo_root()
    input_path = Path(args.input) if args.input else root / ".agent-loop/data/project-data.json"
    output_path = Path(args.output) if args.output else root / ".agent-loop/data/data-quality.json"

    snapshot = load_json(input_path)
    state = load_state(root)
    profile = profile_summary(snapshot)
    checks = signal_checks(snapshot)
    gaps: list[str] = []
    evaluated_signals: list[dict[str, object]] = []
    satisfied = 0

    for signal_id in profile["required_signals"]:
        passed, message = checks.get(signal_id, (False, f"unknown quality signal '{signal_id}'"))
        if passed:
            satisfied += 1
        else:
            gaps.append(f"{profile['label']}: {message}")
        evaluated_signals.append(
            {
                "id": signal_id,
                "passed": passed,
                "message": message,
            }
        )

    total_required = len(profile["required_signals"]) or 1
    overall_score = round((satisfied / total_required) * 100)

    status = "ready"
    if overall_score < 70:
        status = "insufficient"
    elif gaps:
        status = "usable-with-gaps"

    quality = {
        "snapshot_path": str(input_path),
        "archetype_profile": profile,
        "overall_score": overall_score,
        "status": status,
        "evaluated_signals": evaluated_signals,
        "missing_signals": [item["id"] for item in evaluated_signals if not item["passed"]],
        "blocking_gaps": gaps,
        "recommendations": [
            "Refresh missing repo or git signals before high-risk edits.",
            "Refresh validation and remote signals before publishing.",
            "Refresh collection and quality artifacts after material repo changes.",
            "Use the active archetype profile to decide which missing signals matter before broad edits.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output_path, quality)
    if not args.no_state:
        state["project_data"]["quality_path"] = relpath(output_path, root)
        state["project_data"]["last_quality_score"] = overall_score
        state["project_data"]["last_quality_status"] = status
        save_state(root, state)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
