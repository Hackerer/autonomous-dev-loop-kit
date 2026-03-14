#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import find_repo_root, load_json, save_json, load_state, save_state, relpath


def add_gap(gaps: list[str], condition: bool, message: str, score: int) -> int:
    if condition:
        return score
    gaps.append(message)
    return 0


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
    gaps: list[str] = []
    score = 0

    repo = snapshot.get("repo", {})
    project = snapshot.get("project", {})
    validation = snapshot.get("validation", {})
    product_context = snapshot.get("product_context", {})
    evidence = snapshot.get("evidence", {})

    score += add_gap(gaps, bool(repo.get("root")), "missing repo root", 10)
    score += add_gap(gaps, bool(repo.get("current_branch")), "missing current branch", 10)
    score += add_gap(gaps, bool(repo.get("remotes")), "missing git remotes", 10)
    score += add_gap(gaps, repo.get("worktree_clean") is not None, "missing worktree cleanliness signal", 10)
    score += add_gap(gaps, bool(project.get("languages")), "missing language detection", 10)
    score += add_gap(gaps, bool(project.get("package_managers") or project.get("runtime_files")), "missing tooling signals", 10)
    score += add_gap(gaps, bool(validation.get("configured_commands")), "missing validation commands", 10)
    score += add_gap(gaps, bool(product_context.get("target_outcome")), "missing target outcome", 10)
    score += add_gap(gaps, bool(product_context.get("constraints")), "missing constraints", 10)
    score += add_gap(gaps, evidence.get("confidence") in {"direct", "derived"}, "low confidence evidence", 10)

    status = "ready"
    if score < 70:
        status = "insufficient"
    elif gaps:
        status = "usable-with-gaps"

    quality = {
        "snapshot_path": str(input_path),
        "overall_score": score,
        "status": status,
        "blocking_gaps": gaps,
        "recommendations": [
            "Refresh missing repo or git signals before high-risk edits.",
            "Refresh validation and remote signals before publishing."
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output_path, quality)
    if not args.no_state:
        state["project_data"]["quality_path"] = relpath(output_path, root)
        state["project_data"]["last_quality_score"] = score
        state["project_data"]["last_quality_status"] = status
        save_state(root, state)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
