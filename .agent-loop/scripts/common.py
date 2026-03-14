#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_MARKER = ".agent-loop"
CONFIG_FILE = "config.json"
STATE_FILE = "state.json"
BACKLOG_FILE = "backlog.json"
LAST_VALIDATION_FILE = "last-validation.json"


class LoopError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def find_repo_root(start: str | None = None) -> Path:
    path = Path(start or os.getcwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ROOT_MARKER).is_dir():
            return candidate
    raise LoopError(f"Unable to find repo root containing {ROOT_MARKER} from {path}")


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is None:
            raise LoopError(f"Missing required file: {path}")
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True, indent=2)
        handle.write("\n")


def relpath(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def default_state() -> dict[str, Any]:
    return {
        "iteration": 0,
        "status": "idle",
        "session": {
            "status": "not_configured",
            "target_iterations": None,
            "completed_iterations": 0,
            "started_at": None,
            "ended_at": None,
        },
        "project_data": {
            "snapshot_path": None,
            "quality_path": None,
            "last_collected_at": None,
            "last_quality_score": None,
            "last_quality_status": None,
        },
        "current_goal": None,
        "draft_iteration": None,
        "draft_report": None,
        "draft_goal": None,
        "last_report": None,
        "last_validation": {"status": "not_run", "ran_at": None, "results": []},
        "consecutive_failures": 0,
        "history": [],
    }


def load_state(root: Path) -> dict[str, Any]:
    path = root / ROOT_MARKER / STATE_FILE
    state = load_json(path, default=default_state())
    if not isinstance(state, dict):
        raise LoopError(f"State file must contain an object: {path}")
    merged = default_state()
    merged.update(state)

    session = merged.get("session")
    if not isinstance(session, dict):
        session = {}
    default_session = default_state()["session"]
    normalized_session = dict(default_session)
    normalized_session.update(session)
    merged["session"] = normalized_session

    project_data = merged.get("project_data")
    if not isinstance(project_data, dict):
        project_data = {}
    default_project_data = default_state()["project_data"]
    normalized_project_data = dict(default_project_data)
    normalized_project_data.update(project_data)
    merged["project_data"] = normalized_project_data

    last_validation = merged.get("last_validation")
    if not isinstance(last_validation, dict):
        last_validation = {}
    default_validation = default_state()["last_validation"]
    normalized_validation = dict(default_validation)
    normalized_validation.update(last_validation)
    merged["last_validation"] = normalized_validation
    return merged


def save_state(root: Path, state: dict[str, Any]) -> None:
    save_json(root / ROOT_MARKER / STATE_FILE, state)


def load_config(root: Path) -> dict[str, Any]:
    path = root / ROOT_MARKER / CONFIG_FILE
    config = load_json(path)
    if not isinstance(config, dict):
        raise LoopError(f"Config file must contain an object: {path}")
    return config


def planning_config(config: dict[str, Any]) -> dict[str, Any]:
    planning = config.get("planning", {})
    if not isinstance(planning, dict):
        return {}
    return planning


def load_backlog(root: Path) -> list[dict[str, Any]]:
    path = root / ROOT_MARKER / BACKLOG_FILE
    backlog = load_json(path, default=[])
    if not isinstance(backlog, list):
        raise LoopError(f"Backlog file must contain a list: {path}")
    return backlog


def save_backlog(root: Path, backlog: list[dict[str, Any]]) -> None:
    save_json(root / ROOT_MARKER / BACKLOG_FILE, backlog)


def trim_output(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 100] + "\n...[truncated]...\n" + text[-80:]


def run_shell(command: str, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": trim_output(completed.stdout),
        "stderr": trim_output(completed.stderr),
    }


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )


def ensure_git_repo(root: Path) -> None:
    probe = git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        raise LoopError(f"{root} is not inside a Git repository")


def current_branch(root: Path) -> str:
    result = git(root, "branch", "--show-current")
    if result.returncode != 0:
        raise LoopError(result.stderr.strip() or "Unable to read current branch")
    return result.stdout.strip()


def remote_exists(root: Path, remote: str) -> bool:
    result = git(root, "remote")
    if result.returncode != 0:
        return False
    return remote in {line.strip() for line in result.stdout.splitlines() if line.strip()}


def git_remotes(root: Path) -> dict[str, list[str]]:
    result = git(root, "remote", "-v")
    if result.returncode != 0:
        return {}

    remotes: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        url = parts[1].strip()
        remotes.setdefault(name, [])
        if url not in remotes[name]:
            remotes[name].append(url)
    return remotes


def slugify(value: str, max_length: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_length] or "iteration"


def goal_title(goal: Any) -> str:
    if isinstance(goal, dict):
        return str(goal.get("title") or goal.get("id") or "unspecified goal")
    if goal:
        return str(goal)
    return "unspecified goal"


def session_summary(state: dict[str, Any]) -> dict[str, Any]:
    session = state.get("session")
    if not isinstance(session, dict):
        session = {}
    target = session.get("target_iterations")
    completed = int(session.get("completed_iterations", 0) or 0)
    return {
        "status": session.get("status", "not_configured"),
        "target_iterations": target,
        "completed_iterations": completed,
        "remaining_iterations": None if target is None else max(int(target) - completed, 0),
        "started_at": session.get("started_at"),
        "ended_at": session.get("ended_at"),
    }


def require_session_capacity(config: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    planning = planning_config(config)
    session = session_summary(state)
    require_explicit = bool(planning.get("require_explicit_target_iterations", False))
    target = session["target_iterations"]
    completed = session["completed_iterations"]

    if target is None:
        if require_explicit:
            raise LoopError(
                "Loop target is not configured. Run `python3 .agent-loop/scripts/set-loop-session.py --iterations N` before selecting the next goal."
            )
        fallback_limit = planning.get("max_iterations_per_session")
        if fallback_limit is not None and completed >= int(fallback_limit):
            raise LoopError(f"Loop limit reached for this session ({completed}/{int(fallback_limit)}).")
        return session

    target = int(target)
    if completed >= target:
        raise LoopError(f"Loop limit reached for this session ({completed}/{target}).")
    return session


def require_green_validation(state: dict[str, Any]) -> dict[str, Any]:
    validation = state.get("last_validation") or {}
    if validation.get("status") != "passed":
        raise LoopError("Full validation has not passed. Run run-full-validation.py before publishing.")
    return validation


def reporting_path(root: Path, config: dict[str, Any], iteration: int) -> Path:
    reporting = config.get("reporting", {})
    directory = reporting.get("directory", "docs/reports")
    pattern = reporting.get("filename_pattern", "v{iteration}.md")
    filename = pattern.format(iteration=iteration)
    return root / directory / filename
