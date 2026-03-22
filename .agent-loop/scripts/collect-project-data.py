#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    cli_info,
    archetype_profile_summary,
    committee_summary,
    discovery_config,
    current_branch,
    git,
    goal_title,
    load_config,
    load_json,
    load_state,
    relpath,
    review_state_matches_goal,
    save_json,
    save_state,
    resolve_execution_roots,
    utc_now,
)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def detect_languages(root: Path) -> list[str]:
    languages: list[str] = []
    if list(root.rglob("*.py")):
        languages.append("python")
    if list(root.rglob("*.ts")) or list(root.rglob("*.tsx")):
        languages.append("typescript")
    if list(root.rglob("*.js")) or list(root.rglob("*.jsx")):
        languages.append("javascript")
    if (root / "Cargo.toml").exists():
        languages.append("rust")
    return languages


def detect_framework_signals(root: Path) -> list[str]:
    signals: list[str] = []
    package_json = read_text(root / "package.json")
    if "\"next\"" in package_json:
        signals.append("nextjs")
    if "\"react\"" in package_json:
        signals.append("react")
    if "\"vite\"" in package_json:
        signals.append("vite")
    if (root / "pyproject.toml").exists():
        signals.append("python-project")
    return signals


def detect_package_managers(root: Path) -> list[str]:
    managers: list[str] = []
    if (root / "package-lock.json").exists():
        managers.append("npm")
    if (root / "pnpm-lock.yaml").exists():
        managers.append("pnpm")
    if (root / "yarn.lock").exists():
        managers.append("yarn")
    if (root / "uv.lock").exists():
        managers.append("uv")
    if (root / "poetry.lock").exists():
        managers.append("poetry")
    return managers


def detect_runtime_files(root: Path) -> list[str]:
    candidates = [
        "package.json",
        "package-lock.json",
        "pyproject.toml",
        "requirements.txt",
        "tsconfig.json",
        "Cargo.toml",
    ]
    return [name for name in candidates if (root / name).exists()]


def detect_tooling_signals(root: Path, languages: list[str], key_paths: list[str]) -> list[str]:
    signals: list[str] = []
    scripts_dir = root / ".agent-loop/scripts"

    if scripts_dir.is_dir() and list(scripts_dir.glob("*.py")):
        signals.append("python-cli-scripts")
    if ".agent-loop" in key_paths:
        signals.append("autonomous-loop-config")
    if ".agents" in key_paths or ".claude" in key_paths:
        signals.append("agent-skills")
    if "python" in languages and not signals and list(root.rglob("*.py")):
        signals.append("python-sources")

    return signals


def detect_key_paths(root: Path) -> list[str]:
    candidates = [
        ".agent-loop",
        ".agents",
        ".claude",
        "docs",
        "src",
        "app",
        "packages",
    ]
    return [name for name in candidates if (root / name).exists()]


def detect_repo_archetype(key_paths: list[str]) -> str:
    if ".agent-loop" in key_paths and (".agents" in key_paths or ".claude" in key_paths):
        return "agent-skill-kit"
    if ".agent-loop" in key_paths:
        return "autonomous-loop-repo"
    return "general-repo"


def parse_target_outcome(root: Path) -> str:
    plans = read_text(root / "PLANS.md")
    capture = False
    lines: list[str] = []
    for raw_line in plans.splitlines():
        line = raw_line.strip()
        if line == "## Target Outcome":
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.startswith("- "):
            lines.append(line[2:])
    return " ".join(lines).strip()


def parse_constraints(root: Path) -> list[str]:
    plans = read_text(root / "PLANS.md")
    capture = False
    lines: list[str] = []
    for raw_line in plans.splitlines():
        line = raw_line.strip()
        if line == "## Non-Negotiable Constraints":
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.startswith("- "):
            lines.append(line[2:])
    return lines


def parse_open_risks(root: Path) -> list[str]:
    plans = read_text(root / "PLANS.md")
    capture = False
    lines: list[str] = []
    for raw_line in plans.splitlines():
        line = raw_line.strip()
        if line == "## Current State":
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and ("risk" in line.lower() or "block" in line.lower()):
            lines.append(line.lstrip("- ").strip())
    return lines


def git_remotes(root: Path) -> list[dict[str, str]]:
    remotes_output = git(root, "remote", "-v")
    remotes: list[dict[str, str]] = []
    if remotes_output.returncode != 0:
        return remotes
    seen: set[tuple[str, str]] = set()
    for line in remotes_output.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        key = (parts[0], parts[1])
        if key in seen:
            continue
        seen.add(key)
        remotes.append({"name": parts[0], "url": parts[1], "scope": parts[2].strip("()")})
    return remotes


def main() -> int:
    parser = argparse.ArgumentParser(description="将项目的首轮数据收集为结构化快照。")
    parser.add_argument("--output", help="生成的项目数据 JSON 输出路径。")
    parser.add_argument("--no-state", action="store_true", help="不把快照元数据持久化到 .agent-loop/state.json。")
    args = parser.parse_args()

    kit_root, target_root, workspace_root = resolve_execution_roots()
    template = load_json(kit_root / ".agent-loop/templates/project-data-template.json")
    config = load_config(kit_root)
    state = load_state(workspace_root)
    current_goal = state.get("current_goal")
    review_state = state.get("review_state", {})

    snapshot = json.loads(json.dumps(template))
    languages = detect_languages(target_root)
    key_paths = detect_key_paths(target_root)
    snapshot["collected_at"] = utc_now()
    snapshot["repo"] = {
        "root": str(target_root),
        "name": target_root.name,
        "current_branch": current_branch(target_root),
        "worktree_clean": git(target_root, "status", "--short").stdout.strip() == "",
        "remotes": git_remotes(target_root),
    }
    snapshot["project"] = {
        "languages": languages,
        "framework_signals": detect_framework_signals(target_root),
        "tooling_signals": detect_tooling_signals(target_root, languages, key_paths),
        "package_managers": detect_package_managers(target_root),
        "runtime_files": detect_runtime_files(target_root),
        "repo_archetype": detect_repo_archetype(key_paths),
        "archetype_profile": {},
        "key_paths": key_paths,
    }
    snapshot["project"]["archetype_profile"] = archetype_profile_summary(
        config,
        repo_archetype=snapshot["project"]["repo_archetype"],
    )
    snapshot["validation"] = {
        "configured_commands": config.get("validation", {}).get("commands", []),
        "blocking_gates": [item.get("name") for item in config.get("validation", {}).get("commands", []) if item.get("required", True)],
        "confidence": "direct",
    }
    discovery = discovery_config(config)
    snapshot["execution_model"] = {
        "react_cycle_required": True,
        "research_required": bool(discovery.get("require_research_before_goal_selection", False)),
        "minimum_research_inputs": int(discovery.get("minimum_research_inputs", 0) or 0),
        "committee_review_required": bool(discovery.get("require_committee_review", False)),
        "post_validation_reflection_required": bool(discovery.get("require_post_validation_reflection", False)),
        "committee_roles": committee_summary(config),
    }
    snapshot["product_context"] = {
        "target_outcome": parse_target_outcome(target_root),
        "constraints": parse_constraints(target_root),
        "open_risks": parse_open_risks(target_root),
    }
    research_gate = review_state.get("research_gate", {})
    councils = review_state.get("councils", {})
    secretariat = review_state.get("secretariat", {})
    scope_decision = review_state.get("scope_decision", {})
    evaluation = review_state.get("evaluation", {})
    experiment = review_state.get("experiment", {})
    escalation = review_state.get("escalation", {})
    snapshot["latest_review_state"] = {
        "status": review_state.get("status", "not_started"),
        "captured_at": review_state.get("captured_at"),
        "goal_id": review_state.get("goal_id"),
        "goal_title": review_state.get("goal_title"),
        "matches_current_goal": review_state_matches_goal(review_state, current_goal),
        "current_goal_id": current_goal.get("id") if isinstance(current_goal, dict) else None,
        "current_goal_title": goal_title(current_goal) if current_goal else None,
        "research_gate": {
            "status": research_gate.get("status", "not_started") if isinstance(research_gate, dict) else "not_started",
            "summary": research_gate.get("summary", "") if isinstance(research_gate, dict) else "",
            "data_quality_score": research_gate.get("data_quality_score") if isinstance(research_gate, dict) else None,
            "open_gaps": list(research_gate.get("open_gaps", [])) if isinstance(research_gate, dict) else [],
        },
        "council_status": {
            "product_council": councils.get("product_council", {}).get("status", "not_started") if isinstance(councils, dict) else "not_started",
            "architecture_council": councils.get("architecture_council", {}).get("status", "not_started") if isinstance(councils, dict) else "not_started",
            "operator_council": councils.get("operator_council", {}).get("status", "not_started") if isinstance(councils, dict) else "not_started",
        },
        "secretariat": {
            "delivery_secretary": {
                "status": secretariat.get("delivery_secretary", {}).get("status", "not_started")
                if isinstance(secretariat, dict)
                else "not_started",
                "summary": secretariat.get("delivery_secretary", {}).get("summary", "")
                if isinstance(secretariat, dict)
                else "",
                "next_action": secretariat.get("delivery_secretary", {}).get("next_action", "")
                if isinstance(secretariat, dict)
                else "",
            },
            "audit_secretary": {
                "status": secretariat.get("audit_secretary", {}).get("status", "not_started")
                if isinstance(secretariat, dict)
                else "not_started",
                "summary": secretariat.get("audit_secretary", {}).get("summary", "")
                if isinstance(secretariat, dict)
                else "",
                "decision_record": secretariat.get("audit_secretary", {}).get("decision_record", "")
                if isinstance(secretariat, dict)
                else "",
                "open_gaps": list(secretariat.get("audit_secretary", {}).get("open_gaps", []))
                if isinstance(secretariat, dict)
                else [],
            },
        },
        "scope_decision": {
            "status": scope_decision.get("status", "not_started") if isinstance(scope_decision, dict) else "not_started",
            "selected_goal": scope_decision.get("selected_goal", "") if isinstance(scope_decision, dict) else "",
            "scope_in_count": len(scope_decision.get("scope_in", [])) if isinstance(scope_decision, dict) else 0,
            "scope_out_count": len(scope_decision.get("scope_out", [])) if isinstance(scope_decision, dict) else 0,
            "required_validation": list(scope_decision.get("required_validation", [])) if isinstance(scope_decision, dict) else [],
            "stop_conditions": list(scope_decision.get("stop_conditions", [])) if isinstance(scope_decision, dict) else [],
            "dissent_count": len(scope_decision.get("dissent", [])) if isinstance(scope_decision, dict) else 0,
        },
        "evaluation": {
            "status": evaluation.get("status", "not_started") if isinstance(evaluation, dict) else "not_started",
            "rubric_version": evaluation.get("rubric_version", "") if isinstance(evaluation, dict) else "",
            "weighted_score": evaluation.get("weighted_score") if isinstance(evaluation, dict) else None,
            "result": evaluation.get("result", "pending") if isinstance(evaluation, dict) else "pending",
        },
        "experiment": {
            "status": experiment.get("status", "not_started") if isinstance(experiment, dict) else "not_started",
            "base": {
                "label": experiment.get("base", {}).get("label", "") if isinstance(experiment, dict) else "",
                "metric_name": experiment.get("base", {}).get("metric_name", "") if isinstance(experiment, dict) else "",
                "metric_value": experiment.get("base", {}).get("metric_value") if isinstance(experiment, dict) else None,
            },
            "candidate": {
                "label": experiment.get("candidate", {}).get("label", "") if isinstance(experiment, dict) else "",
                "metric_name": experiment.get("candidate", {}).get("metric_name", "") if isinstance(experiment, dict) else "",
                "metric_value": experiment.get("candidate", {}).get("metric_value") if isinstance(experiment, dict) else None,
            },
            "comparison": {
                "status": experiment.get("comparison", {}).get("status", "not_started") if isinstance(experiment, dict) else "not_started",
                "direction": experiment.get("comparison", {}).get("direction", "higher") if isinstance(experiment, dict) else "higher",
                "delta": experiment.get("comparison", {}).get("delta") if isinstance(experiment, dict) else None,
                "result": experiment.get("comparison", {}).get("result", "pending") if isinstance(experiment, dict) else "pending",
                "rationale": experiment.get("comparison", {}).get("rationale", "") if isinstance(experiment, dict) else "",
            },
            "promotion": {
                "status": experiment.get("promotion", {}).get("status", "not_started") if isinstance(experiment, dict) else "not_started",
                "decision": experiment.get("promotion", {}).get("decision", "pending") if isinstance(experiment, dict) else "pending",
                "reason": experiment.get("promotion", {}).get("reason", "") if isinstance(experiment, dict) else "",
                "next_action": experiment.get("promotion", {}).get("next_action", "") if isinstance(experiment, dict) else "",
            },
        },
        "escalation": {
            "status": escalation.get("status", "not_needed") if isinstance(escalation, dict) else "not_needed",
            "reason": escalation.get("reason", "") if isinstance(escalation, dict) else "",
        },
    }
    snapshot["evidence"] = {
        "sources": [
            "PLANS.md",
            ".agent-loop/config.json",
            ".agent-loop/state.json",
            "git status",
            "git remote -v",
        ],
        "freshness": "direct",
        "confidence": "direct",
        "gaps": [],
    }
    snapshot["notes"] = [
        "This snapshot is a first-pass repo scan and should be refreshed after major structural changes."
    ]

    output = Path(args.output) if args.output else workspace_root / ".agent-loop/data/project-data.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, snapshot)
    if not args.no_state:
        state["project_data"]["snapshot_path"] = relpath(output, workspace_root)
        state["project_data"]["last_collected_at"] = snapshot["collected_at"]
        save_state(workspace_root, state)
    cli_info(f"项目数据快照已写入：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
