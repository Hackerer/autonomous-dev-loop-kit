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
EXPECTED_COMMITTEE_ROLE_IDS = ("product-manager", "technical-architect", "user")
EXPECTED_COUNCIL_IDS = ("product-council", "architecture-council", "operator-council")
EXPECTED_SECRETARIAT_PERSONA_IDS = ("delivery-secretary", "audit-secretary")
EXPECTED_EVALUATOR_PERSONA_ID = "independent-evaluator"


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
        "review_state": {
            "status": "not_started",
            "captured_at": None,
            "research_findings": [],
            "committee_feedback": [],
            "committee_decision": [],
            "reflection_notes": [],
        },
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

    review_state = merged.get("review_state")
    if not isinstance(review_state, dict):
        review_state = {}
    default_review_state = default_state()["review_state"]
    normalized_review_state = dict(default_review_state)
    normalized_review_state.update(review_state)
    for key in ("research_findings", "committee_feedback", "committee_decision", "reflection_notes"):
        value = normalized_review_state.get(key)
        if not isinstance(value, list):
            normalized_review_state[key] = []
    merged["review_state"] = normalized_review_state

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


def discovery_config(config: dict[str, Any]) -> dict[str, Any]:
    discovery = config.get("discovery", {})
    if not isinstance(discovery, dict):
        return {}
    return discovery


def committee_config(config: dict[str, Any]) -> dict[str, Any]:
    committee = config.get("committee", {})
    if not isinstance(committee, dict):
        return {}
    return committee


def validate_committee(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    discovery = discovery_config(config)
    committee = committee_config(config)
    enabled = bool(committee.get("enabled", False))
    roles = committee.get("roles", [])

    if discovery.get("require_research_before_goal_selection", False):
        minimum_inputs = int(discovery.get("minimum_research_inputs", 0) or 0)
        if minimum_inputs < 1:
            errors.append("discovery.minimum_research_inputs must be >= 1 when research is required")

    if discovery.get("require_committee_review", False) and not enabled:
        errors.append("committee.enabled must be true when discovery.require_committee_review is true")

    if not enabled:
        return errors

    if not isinstance(roles, list):
        errors.append("committee.roles must be a list")
        return errors

    role_map: dict[str, Any] = {}
    for role in roles:
        if not isinstance(role, dict):
            errors.append("committee.roles entries must be objects")
            continue
        role_id = str(role.get("id", "")).strip()
        if not role_id:
            errors.append("committee.roles entries must include an id")
            continue
        role_map[role_id] = role

    missing_roles = [role_id for role_id in EXPECTED_COMMITTEE_ROLE_IDS if role_id not in role_map]
    if missing_roles:
        errors.append(f"committee.roles is missing required role ids: {', '.join(missing_roles)}")

    for role_id, role in role_map.items():
        members = role.get("members", [])
        if not str(role.get("label", "")).strip():
            errors.append(f"committee role '{role_id}' is missing label")
        if not str(role.get("responsibility", "")).strip():
            errors.append(f"committee role '{role_id}' is missing responsibility")
        if not isinstance(members, list):
            errors.append(f"committee role '{role_id}' members must be a list")
            continue
        if not 3 <= len(members) <= 5:
            errors.append(f"committee role '{role_id}' must define between 3 and 5 members")
        for index, member in enumerate(members, start=1):
            if not isinstance(member, dict):
                errors.append(f"committee role '{role_id}' member {index} must be an object")
                continue
            for key in ("name", "style", "focus"):
                if not str(member.get(key, "")).strip():
                    errors.append(f"committee role '{role_id}' member {index} is missing {key}")

    personas = committee.get("personas")
    councils = committee.get("councils")
    secretariat = committee.get("secretariat")
    evaluator = committee.get("evaluator")
    escalation_policy = committee.get("escalation_policy")

    if personas is not None and not isinstance(personas, dict):
        errors.append("committee.personas must be an object when provided")
        personas = {}
    if councils is not None and not isinstance(councils, list):
        errors.append("committee.councils must be a list when provided")
        councils = []

    persona_map: dict[str, Any] = personas if isinstance(personas, dict) else {}
    for persona_id, persona in persona_map.items():
        if not isinstance(persona, dict):
            errors.append(f"committee persona '{persona_id}' must be an object")
            continue
        for key in ("label", "group", "responsibility", "focus"):
            if not str(persona.get(key, "")).strip():
                errors.append(f"committee persona '{persona_id}' is missing {key}")
        output_fields = persona.get("output_fields", [])
        if not isinstance(output_fields, list) or not output_fields:
            errors.append(f"committee persona '{persona_id}' must define a non-empty output_fields list")

    if isinstance(councils, list):
        council_map: dict[str, Any] = {}
        for council in councils:
            if not isinstance(council, dict):
                errors.append("committee.councils entries must be objects")
                continue
            council_id = str(council.get("id", "")).strip()
            if not council_id:
                errors.append("committee.councils entries must include an id")
                continue
            council_map[council_id] = council
            if not str(council.get("label", "")).strip():
                errors.append(f"committee council '{council_id}' is missing label")
            if not str(council.get("responsibility", "")).strip():
                errors.append(f"committee council '{council_id}' is missing responsibility")
            persona_ids = council.get("persona_ids", [])
            if not isinstance(persona_ids, list) or len(persona_ids) < 1:
                errors.append(f"committee council '{council_id}' must define persona_ids")
                continue
            for persona_id in persona_ids:
                if str(persona_id) not in persona_map:
                    errors.append(f"committee council '{council_id}' references unknown persona '{persona_id}'")

        missing_councils = [council_id for council_id in EXPECTED_COUNCIL_IDS if council_id not in council_map]
        if councils and missing_councils:
            errors.append(f"committee.councils is missing required ids: {', '.join(missing_councils)}")

    if secretariat is not None:
        if not isinstance(secretariat, dict):
            errors.append("committee.secretariat must be an object when provided")
        else:
            persona_ids = secretariat.get("persona_ids", [])
            if not isinstance(persona_ids, list):
                errors.append("committee.secretariat.persona_ids must be a list")
            else:
                for persona_id in EXPECTED_SECRETARIAT_PERSONA_IDS:
                    if persona_id not in persona_ids:
                        errors.append(f"committee.secretariat.persona_ids is missing required persona '{persona_id}'")
                for persona_id in persona_ids:
                    if str(persona_id) not in persona_map:
                        errors.append(f"committee.secretariat references unknown persona '{persona_id}'")

    if evaluator is not None:
        if not isinstance(evaluator, dict):
            errors.append("committee.evaluator must be an object when provided")
        else:
            persona_id = str(evaluator.get("persona_id", "")).strip()
            if persona_id != EXPECTED_EVALUATOR_PERSONA_ID:
                errors.append(
                    f"committee.evaluator.persona_id must be '{EXPECTED_EVALUATOR_PERSONA_ID}' when provided"
                )
            elif persona_id not in persona_map:
                errors.append(f"committee.evaluator references unknown persona '{persona_id}'")
            if not str(evaluator.get("rubric_ref", "")).strip():
                errors.append("committee.evaluator.rubric_ref is required when evaluator is provided")
            thresholds = evaluator.get("result_thresholds", {})
            if not isinstance(thresholds, dict):
                errors.append("committee.evaluator.result_thresholds must be an object")
            else:
                for threshold_key in ("pass", "revise", "fail"):
                    if threshold_key not in thresholds:
                        errors.append(f"committee.evaluator.result_thresholds is missing '{threshold_key}'")

    if escalation_policy is not None:
        if not isinstance(escalation_policy, dict):
            errors.append("committee.escalation_policy must be an object when provided")
        else:
            for key in ("repeat_evaluator_revise_or_fail", "repeat_validation_failures", "repeat_goal_churn"):
                value = escalation_policy.get(key)
                if not isinstance(value, int) or value < 1:
                    errors.append(f"committee.escalation_policy.{key} must be a positive integer when provided")
    return errors


def committee_summary(config: dict[str, Any]) -> list[dict[str, Any]]:
    committee = committee_config(config)
    roles = committee.get("roles", [])
    if not isinstance(roles, list):
        return []
    summary: list[dict[str, Any]] = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        members = role.get("members", [])
        if not isinstance(members, list):
            members = []
        summary.append(
            {
                "id": str(role.get("id", "")),
                "label": str(role.get("label", "") or role.get("id", "committee role")),
                "responsibility": str(role.get("responsibility", "")),
                "member_count": len(members),
                "members": [str(member.get("name", "")) for member in members if isinstance(member, dict)],
            }
        )
    return summary


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


def review_state_matches_goal(review_state: Any, goal: Any) -> bool:
    if not isinstance(review_state, dict):
        return False
    if review_state.get("status") != "captured":
        return False
    if goal is None:
        return True

    review_goal_id = str(review_state.get("goal_id") or "").strip()
    review_goal_title = str(review_state.get("goal_title") or "").strip()

    if isinstance(goal, dict):
        goal_id = str(goal.get("id") or "").strip()
        goal_name = str(goal.get("title") or goal.get("id") or "").strip()
    else:
        goal_id = ""
        goal_name = str(goal or "").strip()

    if goal_id and review_goal_id:
        return goal_id == review_goal_id
    if goal_name and review_goal_title:
        return goal_name == review_goal_title
    return not review_goal_id and not review_goal_title


def require_review_state(config: dict[str, Any], state: dict[str, Any], goal: Any) -> dict[str, Any]:
    discovery = discovery_config(config)
    if not discovery.get("require_committee_review", False):
        review_state = state.get("review_state")
        return review_state if isinstance(review_state, dict) else {}

    review_state = state.get("review_state")
    if not isinstance(review_state, dict) or not review_state_matches_goal(review_state, goal):
        raise LoopError(
            "Recorded review state is missing or does not match the active goal. Run `python3 .agent-loop/scripts/capture-review.py ...` before reporting or publishing."
        )

    has_content = any(
        review_state.get(key)
        for key in ("research_findings", "committee_feedback", "committee_decision", "reflection_notes")
    )
    if not has_content:
        raise LoopError(
            "Recorded review state is empty for the active goal. Capture research, committee feedback, or a decision before reporting or publishing."
        )
    return review_state


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
