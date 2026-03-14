#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    current_branch,
    find_repo_root,
    git,
    load_config,
    load_json,
    load_state,
    relpath,
    save_json,
    save_state,
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
    parser = argparse.ArgumentParser(description="Collect first-pass project data into a structured snapshot.")
    parser.add_argument("--output", help="Output path for the generated project data JSON.")
    parser.add_argument("--no-state", action="store_true", help="Do not persist snapshot metadata into .agent-loop/state.json.")
    args = parser.parse_args()

    root = find_repo_root()
    template = load_json(root / ".agent-loop/templates/project-data-template.json")
    config = load_config(root)
    state = load_state(root)

    snapshot = json.loads(json.dumps(template))
    languages = detect_languages(root)
    key_paths = detect_key_paths(root)
    snapshot["collected_at"] = utc_now()
    snapshot["repo"] = {
        "root": str(root),
        "name": root.name,
        "current_branch": current_branch(root),
        "worktree_clean": git(root, "status", "--short").stdout.strip() == "",
        "remotes": git_remotes(root),
    }
    snapshot["project"] = {
        "languages": languages,
        "framework_signals": detect_framework_signals(root),
        "tooling_signals": detect_tooling_signals(root, languages, key_paths),
        "package_managers": detect_package_managers(root),
        "runtime_files": detect_runtime_files(root),
        "repo_archetype": detect_repo_archetype(key_paths),
        "key_paths": key_paths,
    }
    snapshot["validation"] = {
        "configured_commands": config.get("validation", {}).get("commands", []),
        "blocking_gates": [item.get("name") for item in config.get("validation", {}).get("commands", []) if item.get("required", True)],
        "confidence": "direct",
    }
    snapshot["product_context"] = {
        "target_outcome": parse_target_outcome(root),
        "constraints": parse_constraints(root),
        "open_risks": parse_open_risks(root),
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

    output = Path(args.output) if args.output else root / ".agent-loop/data/project-data.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, snapshot)
    if not args.no_state:
        state["project_data"]["snapshot_path"] = relpath(output, root)
        state["project_data"]["last_collected_at"] = snapshot["collected_at"]
        save_state(root, state)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
