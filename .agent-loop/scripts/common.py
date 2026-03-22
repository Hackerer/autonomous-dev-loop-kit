#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
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
DEFAULT_USAGE_LOG_PATH = ".agent-loop/data/usage-log.jsonl"
PROJECTS_INDEX_FILE = "index.json"
PLACEHOLDER_SNIPPETS = (
    "Summarize the current repo state before this version.",
    "Summarize the repo, product, user, and architecture research completed before selecting this version.",
    "Record the delivery and audit secretary outcome for this iteration.",
    "Document the acceptance criteria for this task iteration.",
    "Capture the evidence or observation that most influenced this task iteration.",
    "List the concrete changes delivered in this task iteration.",
    "Reflect on requirement clarity and architectural impact.",
    "Propose the next highest-value task inside the current release or the next release theme.",
    "Document why this bundled release exists and what user-facing package it represents.",
    "Record the release-level in-scope items.",
    "Record the release-level out-of-scope items.",
    "Record the deferred items that stay out of this release.",
    "Summarize what this release delivered across the included task iterations.",
    "Record the release-level acceptance criteria for this bundled version.",
    "Record the validation results that prove this release is technically sound.",
    "Explain the notable outputs, operator-visible behavior, and architectural consequences of this release.",
    "Document the next bundled release theme or reason to stop.",
)
EXPECTED_COMMITTEE_ROLE_IDS = ("product-manager", "technical-architect", "user")
EXPECTED_COUNCIL_IDS = ("product-council", "architecture-council", "operator-council")
EXPECTED_SECRETARIAT_PERSONA_IDS = ("delivery-secretary", "audit-secretary")
EXPECTED_EVALUATOR_PERSONA_ID = "independent-evaluator"
EXPECTED_ARCHETYPE_SIGNAL_IDS = (
    "collection_timestamp",
    "repo_root",
    "git_branch",
    "git_remote",
    "worktree_clean",
    "languages",
    "tooling_signals",
    "repo_archetype",
    "validation_commands",
    "target_outcome",
    "constraints",
    "direct_evidence",
)


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


def kit_root() -> Path:
    return Path(__file__).resolve().parents[2]


def projects_index_path(kit: Path) -> Path:
    return kit.resolve() / "docs" / "projects" / PROJECTS_INDEX_FILE


def project_root(start: str | None = None) -> Path:
    if start is not None:
        return Path(start).resolve()
    env_target = str(os.environ.get("AUTONOMOUS_DEV_LOOP_TARGET", "")).strip()
    if env_target:
        return Path(env_target).expanduser().resolve()
    return Path(os.getcwd()).resolve()


def project_key(root: Path) -> str:
    resolved = root.resolve()
    fingerprint = project_fingerprint(resolved)
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", project_label(resolved).lower()).strip("-") or "project"
    slug = re.sub(r"-{2,}", "-", slug)
    return f"{slug}-{digest}"


def git_remote_url(root: Path) -> str:
    if not (root / ".git").exists():
        return ""
    for command in (
        ("remote", "get-url", "origin"),
        ("remote", "-v"),
    ):
        result = git(root, *command)
        if result.returncode != 0:
            continue
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            continue
        if command == ("remote", "-v"):
            first = lines[0].split()
            if len(first) >= 2:
                return first[1].strip()
        else:
            return lines[0]
    return ""


def project_fingerprint(root: Path) -> str:
    explicit = str(os.environ.get("AUTONOMOUS_DEV_LOOP_PROJECT_ID", "")).strip()
    if explicit:
        return f"explicit:{explicit}"
    remote = git_remote_url(root)
    if remote:
        return f"git-remote:{remote}"
    if (root / ".git").exists():
        result = git(root, "rev-list", "--max-parents=0", "HEAD")
        if result.returncode == 0:
            roots = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if roots:
                return f"git-root-commit:{','.join(roots)}"
        result = git(root, "rev-parse", "--show-toplevel")
        if result.returncode == 0:
            toplevel = result.stdout.strip()
            if toplevel:
                return f"git-root:{toplevel}"
    return f"path:{root.resolve()}"


def project_label(root: Path) -> str:
    remote = git_remote_url(root)
    if remote:
        cleaned = remote.rstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]
        parts = re.split(r"[/:]+", cleaned)
        for part in reversed(parts):
            part = part.strip()
            if part:
                return part
    return root.name or "project"


def load_projects_index(kit: Path) -> dict[str, Any]:
    path = projects_index_path(kit)
    index = load_json(path, default={"version": 1, "projects": []})
    if not isinstance(index, dict):
        return {"version": 1, "projects": []}
    projects = index.get("projects")
    if not isinstance(projects, list):
        projects = []
    return {"version": 1, "projects": projects}


def save_projects_index(kit: Path, index: dict[str, Any]) -> None:
    save_json(projects_index_path(kit), index)


def project_workspace_root(kit: Path, target: Path) -> Path:
    kit_resolved = kit.resolve()
    target_resolved = target.resolve()
    if target_resolved == kit_resolved:
        return kit_resolved
    workspace_override = str(os.environ.get("AUTONOMOUS_DEV_LOOP_WORKSPACE", "")).strip()
    if workspace_override:
        return Path(workspace_override).expanduser().resolve()
    fingerprint = project_fingerprint(target_resolved)
    label = project_label(target_resolved)
    index = load_projects_index(kit_resolved)
    projects = index["projects"]
    target_key = str(target_resolved)
    for entry in projects:
        if not isinstance(entry, dict):
            continue
        if entry.get("target_root") == target_key or entry.get("fingerprint") == fingerprint:
            workspace_value = str(entry.get("workspace", "")).strip()
            if not workspace_value:
                workspace_value = str(kit_resolved / "docs" / "projects" / project_key(target_resolved))
                entry["workspace"] = workspace_value
            entry["target_root"] = target_key
            entry["fingerprint"] = fingerprint
            entry["label"] = label
            entry["last_seen_at"] = utc_now()
            save_projects_index(kit_resolved, index)
            return Path(workspace_value).expanduser().resolve()

    workspace = kit_resolved / "docs" / "projects" / project_key(target_resolved)
    projects.append(
        {
            "project_id": workspace.name,
            "workspace": str(workspace),
            "target_root": target_key,
            "fingerprint": fingerprint,
            "label": label,
            "first_seen_at": utc_now(),
            "last_seen_at": utc_now(),
        }
    )
    save_projects_index(kit_resolved, index)
    return workspace


def resolve_execution_roots(target: str | None = None) -> tuple[Path, Path, Path]:
    kit = kit_root()
    project = project_root(target)
    workspace_override = str(os.environ.get("AUTONOMOUS_DEV_LOOP_WORKSPACE", "")).strip()
    if workspace_override:
        workspace = Path(workspace_override).expanduser().resolve()
    else:
        workspace = project_workspace_root(kit, project)
    return kit, project, workspace


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


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def relpath(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def is_placeholder_text(value: str) -> bool:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return False
    return any(snippet in text for snippet in PLACEHOLDER_SNIPPETS)


def report_placeholder_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    hits: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        candidate = line[2:].strip() if line.startswith("- ") else line
        if is_placeholder_text(candidate):
            hits.append(candidate)
    return hits


def require_no_report_placeholders(path: Path, label: str) -> None:
    hits = report_placeholder_lines(path)
    if hits:
        preview = "; ".join(hits[:3])
        raise LoopError(f"{label} still contains placeholder content: {preview}")


def default_state() -> dict[str, Any]:
    return {
        "iteration": 0,
        "status": "idle",
        "session": {
            "id": None,
            "status": "not_configured",
            "target_releases": None,
            "completed_releases": 0,
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
        "release": {
            "number": None,
            "title": "",
            "summary": "",
            "status": "not_planned",
            "brief": {
                "archetype": "",
                "objective": "",
                "target_user_value": "",
                "why_now": "",
                "packaging_rationale": "",
                "packaging_signals": [],
                "scope_in": [],
                "scope_out": [],
                "release_acceptance": [],
                "launch_story": "",
                "deferred_items": [],
            },
            "goal_ids": [],
            "goal_titles": [],
            "completed_goal_ids": [],
            "task_iterations": [],
            "selected_at": None,
            "published_at": None,
            "report_path": None,
        },
        "draft_iteration": None,
        "draft_report": None,
        "draft_release_report": None,
        "draft_goal": None,
        "review_state": {
            "status": "not_started",
            "captured_at": None,
            "research_findings": [],
            "committee_feedback": [],
            "committee_decision": [],
            "reflection_notes": [],
            "research_gate": {
                "status": "not_started",
                "summary": "",
                "evidence_refs": [],
                "data_quality_score": None,
                "open_gaps": [],
            },
            "councils": {
                "product_council": {
                    "status": "not_started",
                    "summary": "",
                    "decision": "",
                    "dissent": [],
                },
                "architecture_council": {
                    "status": "not_started",
                    "summary": "",
                    "decision": "",
                    "dissent": [],
                },
                "operator_council": {
                    "status": "not_started",
                    "summary": "",
                    "decision": "",
                    "dissent": [],
                },
            },
            "secretariat": {
                "delivery_secretary": {
                    "status": "not_started",
                    "summary": "",
                    "next_action": "",
                },
                "audit_secretary": {
                    "status": "not_started",
                    "summary": "",
                    "decision_record": "",
                    "evidence_refs": [],
                    "open_gaps": [],
                    "dissent_record": [],
                },
            },
            "cross_committee_tensions": [],
            "scope_decision": {
                "status": "not_started",
                "selected_goal": "",
                "why_selected": "",
                "scope_in": [],
                "scope_out": [],
                "assumptions": [],
                "risks": [],
                "required_validation": [],
                "stop_conditions": [],
                "dissent": [],
                "next_action": "",
            },
            "evaluation": {
                "status": "not_started",
                "rubric_version": "",
                "scores": {},
                "weighted_score": None,
                "result": "pending",
                "critique": [],
                "minimum_fixes_required": [],
            },
            "experiment": {
                "status": "not_started",
                "base": {
                    "label": "",
                    "source_release_number": None,
                    "source_iteration": None,
                    "metric_name": "",
                    "metric_value": None,
                    "source_report": "",
                },
                "candidate": {
                    "label": "",
                    "source_goal_id": "",
                    "source_goal_title": "",
                    "metric_name": "",
                    "metric_value": None,
                    "source_report": "",
                },
                "comparison": {
                    "status": "not_started",
                    "direction": "higher",
                    "delta": None,
                    "result": "pending",
                    "rationale": "",
                },
                "promotion": {
                    "status": "not_started",
                    "decision": "pending",
                    "reason": "",
                    "next_action": "",
                },
            },
            "escalation": {
                "status": "not_needed",
                "reason": "",
                "recommended_action": "",
            },
        },
        "last_report": None,
        "last_validation": {"status": "not_run", "ran_at": None, "results": []},
        "consecutive_failures": 0,
        "history": [],
        "release_history": [],
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
    normalized_session["id"] = derive_session_id(normalized_session)
    if normalized_session.get("target_releases") is None and normalized_session.get("target_iterations") is not None:
        normalized_session["target_releases"] = normalized_session.get("target_iterations")
    if (
        int(normalized_session.get("completed_releases", 0) or 0) == 0
        and int(normalized_session.get("completed_iterations", 0) or 0) > 0
        and state.get("release_history") in (None, [])
    ):
        normalized_session["completed_releases"] = normalized_session.get("completed_iterations", 0)
    merged["session"] = normalized_session

    project_data = merged.get("project_data")
    if not isinstance(project_data, dict):
        project_data = {}
    default_project_data = default_state()["project_data"]
    normalized_project_data = dict(default_project_data)
    normalized_project_data.update(project_data)
    merged["project_data"] = normalized_project_data

    release = merged.get("release")
    if not isinstance(release, dict):
        release = {}
    default_release = default_state()["release"]
    normalized_release = dict(default_release)
    normalized_release.update(release)
    brief = normalized_release.get("brief")
    if not isinstance(brief, dict):
        brief = {}
    default_brief = default_release["brief"]
    normalized_brief = dict(default_brief)
    normalized_brief.update(brief)
    for key in ("packaging_signals", "scope_in", "scope_out", "release_acceptance", "deferred_items"):
        value = normalized_brief.get(key)
        if not isinstance(value, list):
            normalized_brief[key] = []
    normalized_release["brief"] = normalized_brief
    for key in ("goal_ids", "goal_titles", "completed_goal_ids", "task_iterations"):
        value = normalized_release.get(key)
        if not isinstance(value, list):
            normalized_release[key] = []
    merged["release"] = normalized_release

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
    research_gate = normalized_review_state.get("research_gate")
    if not isinstance(research_gate, dict):
        research_gate = {}
    default_research_gate = default_review_state["research_gate"]
    normalized_research_gate = dict(default_research_gate)
    normalized_research_gate.update(research_gate)
    for key in ("evidence_refs", "open_gaps"):
        value = normalized_research_gate.get(key)
        if not isinstance(value, list):
            normalized_research_gate[key] = []
    normalized_review_state["research_gate"] = normalized_research_gate

    councils = normalized_review_state.get("councils")
    if not isinstance(councils, dict):
        councils = {}
    default_councils = default_review_state["councils"]
    normalized_councils: dict[str, Any] = {}
    for council_key, default_council in default_councils.items():
        council_value = councils.get(council_key)
        if not isinstance(council_value, dict):
            council_value = {}
        normalized_council = dict(default_council)
        normalized_council.update(council_value)
        dissent = normalized_council.get("dissent")
        if not isinstance(dissent, list):
            normalized_council["dissent"] = []
        normalized_councils[council_key] = normalized_council
    normalized_review_state["councils"] = normalized_councils

    secretariat = normalized_review_state.get("secretariat")
    if not isinstance(secretariat, dict):
        secretariat = {}
    default_secretariat = default_review_state["secretariat"]
    normalized_secretariat: dict[str, Any] = {}
    for secretariat_key, default_secretary in default_secretariat.items():
        secretariat_value = secretariat.get(secretariat_key)
        if not isinstance(secretariat_value, dict):
            secretariat_value = {}
        normalized_secretary = dict(default_secretary)
        normalized_secretary.update(secretariat_value)
        for key in ("evidence_refs", "open_gaps", "dissent_record"):
            if key in normalized_secretary and not isinstance(normalized_secretary.get(key), list):
                normalized_secretary[key] = []
        normalized_secretariat[secretariat_key] = normalized_secretary
    normalized_review_state["secretariat"] = normalized_secretariat

    for key in ("cross_committee_tensions",):
        value = normalized_review_state.get(key)
        if not isinstance(value, list):
            normalized_review_state[key] = []

    scope_decision = normalized_review_state.get("scope_decision")
    if not isinstance(scope_decision, dict):
        scope_decision = {}
    default_scope_decision = default_review_state["scope_decision"]
    normalized_scope_decision = dict(default_scope_decision)
    normalized_scope_decision.update(scope_decision)
    for key in ("scope_in", "scope_out", "assumptions", "risks", "required_validation", "stop_conditions", "dissent"):
        value = normalized_scope_decision.get(key)
        if not isinstance(value, list):
            normalized_scope_decision[key] = []
    normalized_review_state["scope_decision"] = normalized_scope_decision

    evaluation = normalized_review_state.get("evaluation")
    if not isinstance(evaluation, dict):
        evaluation = {}
    default_evaluation = default_review_state["evaluation"]
    normalized_evaluation = dict(default_evaluation)
    normalized_evaluation.update(evaluation)
    critique = normalized_evaluation.get("critique")
    if not isinstance(critique, list):
        normalized_evaluation["critique"] = []
    minimum_fixes_required = normalized_evaluation.get("minimum_fixes_required")
    if not isinstance(minimum_fixes_required, list):
        normalized_evaluation["minimum_fixes_required"] = []
    scores = normalized_evaluation.get("scores")
    if not isinstance(scores, dict):
        normalized_evaluation["scores"] = {}
    normalized_review_state["evaluation"] = normalized_evaluation

    experiment = normalized_review_state.get("experiment")
    if not isinstance(experiment, dict):
        experiment = {}
    default_experiment = default_review_state["experiment"]
    normalized_experiment = dict(default_experiment)
    normalized_experiment.update(experiment)
    for key in ("base", "candidate", "comparison", "promotion"):
        value = normalized_experiment.get(key)
        if not isinstance(value, dict):
            value = {}
        default_value = default_experiment.get(key, {})
        normalized_value = dict(default_value)
        normalized_value.update(value)
        normalized_experiment[key] = normalized_value
    normalized_review_state["experiment"] = normalized_experiment

    escalation = normalized_review_state.get("escalation")
    if not isinstance(escalation, dict):
        escalation = {}
    default_escalation = default_review_state["escalation"]
    normalized_escalation = dict(default_escalation)
    normalized_escalation.update(escalation)
    normalized_review_state["escalation"] = normalized_escalation
    merged["review_state"] = normalized_review_state

    last_validation = merged.get("last_validation")
    if not isinstance(last_validation, dict):
        last_validation = {}
    default_validation = default_state()["last_validation"]
    normalized_validation = dict(default_validation)
    normalized_validation.update(last_validation)
    merged["last_validation"] = normalized_validation

    history = merged.get("history")
    if not isinstance(history, list):
        history = []
    merged["history"] = history

    release_history = merged.get("release_history")
    if not isinstance(release_history, list):
        release_history = []
    merged["release_history"] = release_history
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


def experiment_config(config: dict[str, Any]) -> dict[str, Any]:
    experiment = config.get("experiment", {})
    if not isinstance(experiment, dict):
        experiment = {}
    return {
        "enabled": bool(experiment.get("enabled", True)),
        "baseline_strategy": str(experiment.get("baseline_strategy", "last_promoted_release") or "last_promoted_release"),
        "metric_path": str(experiment.get("metric_path", "review_state.evaluation.weighted_score") or "review_state.evaluation.weighted_score"),
        "direction": str(experiment.get("direction", "higher") or "higher"),
        "allow_equal": bool(experiment.get("allow_equal", False)),
    }


def release_planning_config(config: dict[str, Any]) -> dict[str, Any]:
    planning = planning_config(config)
    release_planning = planning.get("release", {})
    if not isinstance(release_planning, dict):
        release_planning = {}
    min_goals = int(release_planning.get("min_goals_per_release", 2) or 2)
    max_goals = int(release_planning.get("max_goals_per_release", 4) or 4)
    default_goals = int(release_planning.get("default_goals_per_release", min_goals) or min_goals)
    if max_goals < min_goals:
        max_goals = min_goals
    if default_goals < min_goals:
        default_goals = min_goals
    if default_goals > max_goals:
        default_goals = max_goals
    return {
        "require_release_plan": bool(release_planning.get("require_release_plan", True)),
        "min_goals_per_release": min_goals,
        "max_goals_per_release": max_goals,
        "default_goals_per_release": default_goals,
    }


def usage_logging_config(config: dict[str, Any]) -> dict[str, Any]:
    usage_logging = config.get("usage_logging", {})
    if not isinstance(usage_logging, dict):
        usage_logging = {}
    return {
        "enabled": bool(usage_logging.get("enabled", True)),
        "path": str(usage_logging.get("path", DEFAULT_USAGE_LOG_PATH) or DEFAULT_USAGE_LOG_PATH),
    }


def derive_session_id(session: dict[str, Any] | None) -> str | None:
    if not isinstance(session, dict):
        return None
    raw_id = session.get("id")
    if raw_id is not None:
        text = str(raw_id).strip()
        if text and text.lower() != "none":
            return text
    started_at = str(session.get("started_at", "")).strip()
    if not started_at:
        return None
    return f"session-{started_at.replace(':', '').replace('-', '').replace('T', '-').replace('Z', '')}"


def discovery_config(config: dict[str, Any]) -> dict[str, Any]:
    discovery = config.get("discovery", {})
    if not isinstance(discovery, dict):
        return {}
    return discovery


def archetype_profiles_config(config: dict[str, Any]) -> dict[str, Any]:
    discovery = discovery_config(config)
    profiles = discovery.get("archetype_profiles", {})
    if not isinstance(profiles, dict):
        return {}
    return profiles


def archetype_profile_summary(config: dict[str, Any], repo_archetype: str | None = None) -> dict[str, Any]:
    profiles_config = archetype_profiles_config(config)
    profiles = profiles_config.get("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}

    default_profile_id = str(profiles_config.get("default_profile", "baseline")).strip() or "baseline"
    selected_id = default_profile_id
    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        repo_archetypes = profile.get("repo_archetypes", [])
        if repo_archetype and isinstance(repo_archetypes, list) and repo_archetype in [str(item) for item in repo_archetypes]:
            selected_id = str(profile_id)
            break

    selected = profiles.get(selected_id, {})
    if not isinstance(selected, dict):
        selected = {}
    required_signals = selected.get("required_signals", [])
    committee_emphasis = selected.get("committee_emphasis", [])
    return {
        "id": selected_id,
        "label": str(selected.get("label", "") or selected_id),
        "repo_archetypes": [str(item) for item in selected.get("repo_archetypes", []) if str(item).strip()]
        if isinstance(selected.get("repo_archetypes"), list)
        else [],
        "required_signals": [str(item) for item in required_signals if str(item).strip()]
        if isinstance(required_signals, list)
        else [],
        "committee_emphasis": [str(item) for item in committee_emphasis if str(item).strip()]
        if isinstance(committee_emphasis, list)
        else [],
    }


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
    archetype_profiles = archetype_profiles_config(config)

    if discovery.get("require_research_before_goal_selection", False):
        minimum_inputs = int(discovery.get("minimum_research_inputs", 0) or 0)
        if minimum_inputs < 1:
            errors.append("discovery.minimum_research_inputs must be >= 1 when research is required")

    if archetype_profiles:
        default_profile = str(archetype_profiles.get("default_profile", "")).strip()
        profiles = archetype_profiles.get("profiles", {})
        if not isinstance(profiles, dict) or not profiles:
            errors.append("discovery.archetype_profiles.profiles must be a non-empty object when provided")
        else:
            if not default_profile:
                errors.append("discovery.archetype_profiles.default_profile is required when profiles are provided")
            elif default_profile not in profiles:
                errors.append("discovery.archetype_profiles.default_profile must reference a defined profile")
            for profile_id, profile in profiles.items():
                if not isinstance(profile, dict):
                    errors.append(f"discovery.archetype_profiles.profiles.{profile_id} must be an object")
                    continue
                if not str(profile.get("label", "")).strip():
                    errors.append(f"discovery.archetype_profiles.profiles.{profile_id} is missing label")
                repo_archetypes = profile.get("repo_archetypes", [])
                if repo_archetypes is not None and not isinstance(repo_archetypes, list):
                    errors.append(f"discovery.archetype_profiles.profiles.{profile_id}.repo_archetypes must be a list")
                required_signals = profile.get("required_signals", [])
                if not isinstance(required_signals, list) or not required_signals:
                    errors.append(
                        f"discovery.archetype_profiles.profiles.{profile_id}.required_signals must be a non-empty list"
                    )
                else:
                    unknown_signals = [
                        str(signal)
                        for signal in required_signals
                        if str(signal).strip() and str(signal) not in EXPECTED_ARCHETYPE_SIGNAL_IDS
                    ]
                    if unknown_signals:
                        errors.append(
                            f"discovery.archetype_profiles.profiles.{profile_id} uses unknown required_signals: {', '.join(unknown_signals)}"
                        )
                committee_emphasis = profile.get("committee_emphasis", [])
                if committee_emphasis is not None and not isinstance(committee_emphasis, list):
                    errors.append(
                        f"discovery.archetype_profiles.profiles.{profile_id}.committee_emphasis must be a list"
                    )

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
            if "require_pass_before_implementation" in evaluator and not isinstance(
                evaluator.get("require_pass_before_implementation"), bool
            ):
                errors.append("committee.evaluator.require_pass_before_implementation must be a boolean when provided")
            gate_mode = str(evaluator.get("implementation_gate_mode", "blocking")).strip()
            if gate_mode not in {"blocking", "advisory"}:
                errors.append("committee.evaluator.implementation_gate_mode must be 'blocking' or 'advisory'")
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


def persona_catalog(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    committee = committee_config(config)
    personas = committee.get("personas", {})
    if not isinstance(personas, dict):
        return {}
    summary: dict[str, dict[str, Any]] = {}
    for persona_id, persona in personas.items():
        if not isinstance(persona, dict):
            continue
        output_fields = persona.get("output_fields", [])
        if not isinstance(output_fields, list):
            output_fields = []
        release_output_fields = persona.get("release_output_fields", [])
        if not isinstance(release_output_fields, list):
            release_output_fields = []
        summary[str(persona_id)] = {
            "id": str(persona_id),
            "label": str(persona.get("label", "") or persona_id),
            "group": str(persona.get("group", "")),
            "responsibility": str(persona.get("responsibility", "")),
            "focus": str(persona.get("focus", "")),
            "output_fields": [str(item) for item in output_fields if str(item).strip()],
            "release_output_fields": [str(item) for item in release_output_fields if str(item).strip()],
        }
    return summary


def council_summary(config: dict[str, Any]) -> list[dict[str, Any]]:
    committee = committee_config(config)
    councils = committee.get("councils", [])
    personas = persona_catalog(config)
    if not isinstance(councils, list):
        return []
    summary: list[dict[str, Any]] = []
    for council in councils:
        if not isinstance(council, dict):
            continue
        persona_ids = council.get("persona_ids", [])
        if not isinstance(persona_ids, list):
            persona_ids = []
        resolved_personas = [personas[persona_id] for persona_id in persona_ids if str(persona_id) in personas]
        summary.append(
            {
                "id": str(council.get("id", "")),
                "label": str(council.get("label", "") or council.get("id", "council")),
                "responsibility": str(council.get("responsibility", "")),
                "persona_ids": [str(persona_id) for persona_id in persona_ids],
                "personas": resolved_personas,
            }
        )
    return summary


def secretariat_summary(config: dict[str, Any]) -> list[dict[str, Any]]:
    committee = committee_config(config)
    secretariat = committee.get("secretariat", {})
    personas = persona_catalog(config)
    if not isinstance(secretariat, dict):
        return []
    persona_ids = secretariat.get("persona_ids", [])
    if not isinstance(persona_ids, list):
        return []
    return [personas[persona_id] for persona_id in persona_ids if str(persona_id) in personas]


def evaluator_summary(config: dict[str, Any]) -> dict[str, Any]:
    committee = committee_config(config)
    evaluator = committee.get("evaluator", {})
    personas = persona_catalog(config)
    if not isinstance(evaluator, dict):
        return {}
    persona_id = str(evaluator.get("persona_id", "")).strip()
    return {
        "persona": personas.get(persona_id, {}),
        "rubric_ref": str(evaluator.get("rubric_ref", "")),
        "require_pass_before_implementation": bool(evaluator.get("require_pass_before_implementation", False)),
        "implementation_gate_mode": str(evaluator.get("implementation_gate_mode", "blocking")),
        "result_thresholds": evaluator.get("result_thresholds", {}),
    }


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


def safe_current_branch(root: Path) -> str:
    if not root.exists():
        return ""
    try:
        return current_branch(root)
    except LoopError:
        return ""


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


def usage_log_path(root: Path, config: dict[str, Any]) -> Path:
    usage_logging = usage_logging_config(config)
    return root / usage_logging["path"]


def detected_usage_client() -> str | None:
    explicit = str(os.environ.get("AUTONOMOUS_LOOP_CLIENT", "")).strip()
    if explicit:
        return explicit
    for key, label in (
        ("CLAUDECODE", "claude-code"),
        ("CLAUDE_CODE", "claude-code"),
        ("CODEX_HOME", "codex"),
    ):
        value = str(os.environ.get(key, "")).strip()
        if value:
            return label
    return None


def usage_log_context(root: Path) -> dict[str, Any]:
    try:
        state = load_state(root)
    except LoopError:
        return {}

    session = session_summary(state)
    release = release_summary(state)
    goal = state.get("draft_goal") or state.get("current_goal")
    context: dict[str, Any] = {
        "session": {
            "id": session.get("id"),
            "status": session.get("status"),
            "target_releases": session.get("target_releases"),
            "completed_releases": session.get("completed_releases"),
            "completed_iterations": session.get("completed_iterations"),
        },
        "release": {
            "number": release.get("number"),
            "status": release.get("status"),
            "title": release.get("title"),
            "remaining_goal_ids": list(release.get("remaining_goal_ids", [])),
        },
        "goal": {
            "id": goal.get("id"),
            "title": goal_title(goal),
        }
        if isinstance(goal, dict)
        else None,
        "iteration": state.get("draft_iteration") or state.get("iteration"),
        "state_status": state.get("status"),
    }
    return context


def append_usage_log(
    workspace_root: Path,
    config: dict[str, Any],
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    target_root: Path | None = None,
) -> Path | None:
    usage_logging = usage_logging_config(config)
    if not usage_logging["enabled"]:
        return None

    repo_root = target_root or workspace_root
    remotes = git_remotes(repo_root) if (repo_root / ".git").exists() else {}
    context = usage_log_context(workspace_root)
    client = detected_usage_client()
    record = {
        "timestamp": utc_now(),
        "event": str(event_type),
        "workspace": {
            "root": str(workspace_root),
            "name": workspace_root.name,
        },
        "repo": {
            "root": str(repo_root),
            "name": repo_root.name,
            "current_branch": safe_current_branch(repo_root),
            "remotes": remotes,
        },
        "loop_mode": str(config.get("mode", "")),
        "client": client,
        "session": context.get("session", {}),
        "release": context.get("release", {}),
        "goal": context.get("goal"),
        "iteration": context.get("iteration"),
        "state_status": context.get("state_status"),
        "payload": payload if isinstance(payload, dict) else {},
    }
    path = usage_log_path(workspace_root, config)
    append_jsonl(path, record)
    return path


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


def require_selected_goal(state: dict[str, Any]) -> dict[str, Any]:
    goal = state.get("current_goal") or state.get("draft_goal")
    if not isinstance(goal, dict):
        raise LoopError("No active goal is selected. Run `python3 .agent-loop/scripts/select-next-goal.py` first.")
    goal_id = str(goal.get("id", "")).strip()
    goal_name = goal_title(goal)
    if not goal_id or goal_name == "unspecified goal":
        raise LoopError(
            "The active goal is incomplete or unspecified. Select a valid backlog goal before writing reports or publishing."
        )
    return goal


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


def review_state_has_content(review_state: Any) -> bool:
    if not isinstance(review_state, dict):
        return False

    for key in ("research_findings", "committee_feedback", "committee_decision", "reflection_notes"):
        value = review_state.get(key)
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True

    research_gate = review_state.get("research_gate")
    if isinstance(research_gate, dict):
        if str(research_gate.get("summary", "")).strip():
            return True
        for key in ("evidence_refs", "open_gaps"):
            value = research_gate.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                return True
        if research_gate.get("data_quality_score") is not None:
            return True

    councils = review_state.get("councils")
    if isinstance(councils, dict):
        for council in councils.values():
            if not isinstance(council, dict):
                continue
            if str(council.get("summary", "")).strip() or str(council.get("decision", "")).strip():
                return True
            dissent = council.get("dissent")
            if isinstance(dissent, list) and any(str(item).strip() for item in dissent):
                return True

    secretariat = review_state.get("secretariat")
    if isinstance(secretariat, dict):
        for secretary in secretariat.values():
            if not isinstance(secretary, dict):
                continue
            for key in ("summary", "next_action", "decision_record"):
                if str(secretary.get(key, "")).strip():
                    return True
            for key in ("evidence_refs", "open_gaps", "dissent_record"):
                value = secretary.get(key)
                if isinstance(value, list) and any(str(item).strip() for item in value):
                    return True

    scope_decision = review_state.get("scope_decision")
    if isinstance(scope_decision, dict):
        for key in ("selected_goal", "why_selected", "next_action"):
            if str(scope_decision.get(key, "")).strip():
                return True
        for key in ("scope_in", "scope_out", "assumptions", "risks", "required_validation", "stop_conditions", "dissent"):
            value = scope_decision.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                return True

    experiment = review_state.get("experiment")
    if isinstance(experiment, dict):
        if str(experiment.get("status", "")).strip() not in {"", "not_started"}:
            return True
        for slot in ("base", "candidate", "comparison", "promotion"):
            section = experiment.get(slot)
            if not isinstance(section, dict):
                continue
            for key in ("label", "source_goal_id", "source_goal_title", "metric_name", "source_report", "reason", "next_action", "rationale"):
                if str(section.get(key, "")).strip():
                    return True
            for key in ("metric_value", "delta"):
                if section.get(key) is not None:
                    return True
            if slot == "comparison" and str(section.get("result", "")).strip() not in {"", "pending"}:
                return True
            if slot == "promotion" and str(section.get("decision", "")).strip() not in {"", "pending"}:
                return True

    evaluation = review_state.get("evaluation")
    if isinstance(evaluation, dict):
        if str(evaluation.get("rubric_version", "")).strip() or str(evaluation.get("result", "")).strip() not in {"", "pending"}:
            return True
        if evaluation.get("weighted_score") is not None:
            return True
        scores = evaluation.get("scores")
        if isinstance(scores, dict) and any(str(key).strip() for key in scores):
            return True
        for key in ("critique", "minimum_fixes_required"):
            value = evaluation.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                return True

    escalation = review_state.get("escalation")
    if isinstance(escalation, dict):
        for key in ("reason", "recommended_action"):
            if str(escalation.get(key, "")).strip():
                return True
        if str(escalation.get("status", "")).strip() not in {"", "not_needed"}:
            return True

    tensions = review_state.get("cross_committee_tensions")
    if isinstance(tensions, list) and any(str(item).strip() for item in tensions):
        return True

    return False


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

    if not review_state_has_content(review_state):
        raise LoopError(
            "Recorded review state is empty for the active goal. Capture research, committee feedback, or a decision before reporting or publishing."
        )
    return review_state


def require_evaluator_pass(config: dict[str, Any], state: dict[str, Any], goal: Any) -> dict[str, Any]:
    committee = committee_config(config)
    evaluator = committee.get("evaluator", {})
    if not isinstance(evaluator, dict) or not evaluator.get("require_pass_before_implementation", False):
        evaluation = state.get("review_state", {}).get("evaluation")
        return evaluation if isinstance(evaluation, dict) else {}

    review_state = require_review_state(config, state, goal)
    evaluation = review_state.get("evaluation")
    if not isinstance(evaluation, dict):
        raise LoopError(
            "Evaluator result is missing for the active goal. Record a passing evaluator result with `python3 .agent-loop/scripts/capture-review.py ... --evaluation-result pass` before implementation."
        )
    if evaluation.get("status") != "captured":
        raise LoopError(
            "Evaluator result has not been captured for the active goal. Record it with `python3 .agent-loop/scripts/capture-review.py ... --evaluation-result pass` before implementation."
        )
    if str(evaluation.get("result", "")).strip() != "pass":
        raise LoopError(
            "Evaluator result is not pass for the active goal. Resolve the critique and record a passing evaluator result before implementation."
        )
    return evaluation


def implementation_gate_status(config: dict[str, Any], evaluation: dict[str, Any] | None) -> dict[str, str]:
    evaluator = committee_config(config).get("evaluator", {})
    if not isinstance(evaluator, dict):
        evaluator = {}
    gate_mode = str(evaluator.get("implementation_gate_mode", "blocking")).strip() or "blocking"
    result = ""
    status = "pending"
    if isinstance(evaluation, dict):
        result = str(evaluation.get("result", "")).strip()
        if evaluation.get("status") == "captured":
            if result == "pass":
                status = "pass"
            elif result in {"revise", "fail"}:
                status = "warn" if gate_mode == "advisory" else "block"
    return {
        "mode": gate_mode,
        "evaluation_result": result or "pending",
        "status": status,
    }


def session_summary(state: dict[str, Any]) -> dict[str, Any]:
    session = state.get("session")
    if not isinstance(session, dict):
        session = {}
    target_releases = session.get("target_releases")
    completed_releases = int(session.get("completed_releases", 0) or 0)
    target_iterations = session.get("target_iterations")
    completed_iterations = int(session.get("completed_iterations", 0) or 0)
    return {
        "id": derive_session_id(session),
        "status": session.get("status", "not_configured"),
        "target_releases": target_releases,
        "completed_releases": completed_releases,
        "remaining_releases": None if target_releases is None else max(int(target_releases) - completed_releases, 0),
        "target_iterations": target_iterations,
        "completed_iterations": completed_iterations,
        "remaining_iterations": None if target_iterations is None else max(int(target_iterations) - completed_iterations, 0),
        "started_at": session.get("started_at"),
        "ended_at": session.get("ended_at"),
    }


def require_session_capacity(config: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    planning = planning_config(config)
    session = session_summary(state)
    require_explicit = bool(planning.get("require_explicit_target_iterations", False))
    target = session["target_releases"]
    completed = session["completed_releases"]

    if target is None:
        if require_explicit:
            raise LoopError(
                "Release target is not configured. Run `python3 .agent-loop/scripts/set-loop-session.py --iterations N` before selecting the next goal."
            )
        fallback_limit = planning.get("max_releases_per_session", planning.get("max_iterations_per_session"))
        if fallback_limit is not None and completed >= int(fallback_limit):
            raise LoopError(f"Release limit reached for this session ({completed}/{int(fallback_limit)}).")
        return session

    target = int(target)
    if completed >= target:
        raise LoopError(f"Release limit reached for this session ({completed}/{target}).")
    return session


def next_release_number(state: dict[str, Any]) -> int:
    session = session_summary(state)
    session_id = session.get("id")
    history = state.get("release_history", [])
    session_history_count = 0
    if session_id and isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            item_session_id = str(item.get("session_id", "")).strip()
            if item_session_id and item_session_id == session_id:
                session_history_count += 1
    completed_releases = int(session.get("completed_releases", 0) or 0)
    return max(completed_releases, session_history_count) + 1


def active_release(state: dict[str, Any]) -> dict[str, Any]:
    release = state.get("release")
    if not isinstance(release, dict):
        return default_state()["release"]
    return release


def active_release_goal_ids(state: dict[str, Any]) -> list[str]:
    release = active_release(state)
    if str(release.get("status", "")).strip() in {"not_planned", "published"}:
        return []
    return [str(goal_id) for goal_id in release.get("goal_ids", []) if str(goal_id).strip()]


def latest_promoted_release_record(state: dict[str, Any]) -> dict[str, Any] | None:
    history = state.get("history", [])
    if isinstance(history, list):
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            if item.get("candidate_metric_value") is not None or item.get("evaluation_weighted_score") is not None:
                return item
    history = state.get("release_history", [])
    if not isinstance(history, list):
        return None
    for item in reversed(history):
        if isinstance(item, dict):
            return item
    return None


def latest_promoted_metric_value(state: dict[str, Any]) -> float | None:
    record = latest_promoted_release_record(state)
    if not isinstance(record, dict):
        return None
    metric_value = record.get("candidate_metric_value")
    if metric_value is None:
        metric_value = record.get("evaluation_weighted_score")
    try:
        return float(metric_value)
    except (TypeError, ValueError):
        return None


def current_candidate_metric(state: dict[str, Any]) -> float | None:
    review_state = state.get("review_state", {})
    if not isinstance(review_state, dict):
        return None
    experiment = review_state.get("experiment", {})
    if isinstance(experiment, dict):
        candidate = experiment.get("candidate", {})
        if isinstance(candidate, dict) and candidate.get("metric_value") is not None:
            try:
                return float(candidate.get("metric_value"))
            except (TypeError, ValueError):
                return None
    evaluation = review_state.get("evaluation", {})
    if not isinstance(evaluation, dict):
        return None
    metric_value = evaluation.get("weighted_score")
    try:
        return float(metric_value)
    except (TypeError, ValueError):
        return None


def experiment_status(state: dict[str, Any]) -> dict[str, Any]:
    review_state = state.get("review_state", {})
    experiment = {}
    if isinstance(review_state, dict):
        experiment = review_state.get("experiment", {})
    if not isinstance(experiment, dict) or not experiment:
        experiment = state.get("experiment", {})
    if not isinstance(experiment, dict):
        experiment = {}
    default_experiment = default_state()["review_state"]["experiment"]
    normalized = dict(default_experiment)
    normalized.update(experiment)
    for key in ("base", "candidate", "comparison", "promotion"):
        value = normalized.get(key)
        if not isinstance(value, dict):
            value = {}
        default_value = default_experiment.get(key, {})
        normalized_value = dict(default_value)
        normalized_value.update(value)
        normalized[key] = normalized_value
    return normalized


def promote_candidate_decision(state: dict[str, Any], allow_equal: bool = False) -> tuple[bool, str, float | None, float | None]:
    experiment = experiment_status(state)
    promotion = experiment.get("promotion", {})
    comparison = experiment.get("comparison", {})
    if not isinstance(promotion, dict):
        promotion = {}
    if not isinstance(comparison, dict):
        comparison = {}

    explicit_decision = str(promotion.get("decision", "")).strip()
    explicit_reason = str(promotion.get("reason", "")).strip()
    if explicit_decision in {"discard", "revise"}:
        return False, explicit_reason or f"Experiment decision is {explicit_decision}.", None, None

    baseline_value = latest_promoted_metric_value(state)
    candidate_value = current_candidate_metric(state)
    direction = str(comparison.get("direction", "higher")).strip() or "higher"

    if baseline_value is None or candidate_value is None:
        return True, "No comparable baseline metric exists yet, so the candidate becomes the first promoted base.", baseline_value, candidate_value

    if direction == "lower":
        better = candidate_value < baseline_value or (allow_equal and candidate_value == baseline_value)
        if better:
            return True, explicit_reason or f"Candidate metric {candidate_value} is lower than baseline {baseline_value}.", baseline_value, candidate_value
        return False, f"Candidate metric {candidate_value} does not improve on baseline {baseline_value}.", baseline_value, candidate_value

    better = candidate_value > baseline_value or (allow_equal and candidate_value == baseline_value)
    if better:
        return True, explicit_reason or f"Candidate metric {candidate_value} improves on baseline {baseline_value}.", baseline_value, candidate_value
    return False, f"Candidate metric {candidate_value} does not improve on baseline {baseline_value}.", baseline_value, candidate_value


def release_summary(state: dict[str, Any]) -> dict[str, Any]:
    release = active_release(state)
    goal_ids = [str(goal_id) for goal_id in release.get("goal_ids", []) if str(goal_id).strip()]
    completed_goal_ids = [str(goal_id) for goal_id in release.get("completed_goal_ids", []) if str(goal_id).strip()]
    number = release.get("number")
    return {
        "number": number,
        "title": str(release.get("title", "")).strip(),
        "summary": str(release.get("summary", "")).strip(),
        "status": str(release.get("status", "not_planned")).strip() or "not_planned",
        "brief": release.get("brief", {}) if isinstance(release.get("brief"), dict) else {},
        "goal_ids": goal_ids,
        "goal_titles": [str(title) for title in release.get("goal_titles", []) if str(title).strip()],
        "completed_goal_ids": completed_goal_ids,
        "remaining_goal_ids": [goal_id for goal_id in goal_ids if goal_id not in completed_goal_ids],
        "selected_at": release.get("selected_at"),
        "published_at": release.get("published_at"),
        "report_path": release.get("report_path"),
        "task_iterations": release.get("task_iterations", []) if isinstance(release.get("task_iterations"), list) else [],
    }


def require_active_release(config: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    release_cfg = release_planning_config(config)
    release = release_summary(state)
    if release_cfg["require_release_plan"] and release["status"] in {"not_planned", "published"}:
        raise LoopError(
            "No active release plan exists. Define the next bundled version first with `python3 .agent-loop/scripts/plan-release.py`."
        )
    return release


def require_goal_in_active_release(config: dict[str, Any], state: dict[str, Any], goal: dict[str, Any]) -> dict[str, Any]:
    release = require_active_release(config, state)
    goal_id = str(goal.get("id", "")).strip()
    if release["number"] is None or not goal_id:
        raise LoopError("Cannot continue because the active goal is not attached to a valid planned release.")
    if release["goal_ids"] and goal_id not in release["goal_ids"]:
        raise LoopError(
            "The active goal is not part of the active release. Re-select a goal from the current release plan or plan a new release intentionally."
        )
    return release


def release_reporting_path(root: Path, config: dict[str, Any], release_number: int) -> Path:
    reporting = config.get("reporting", {})
    directory = reporting.get("release_directory", "docs/releases")
    pattern = reporting.get("release_filename_pattern", "R{release}.md")
    filename = pattern.format(release=release_number)
    return root / directory / filename


def goal_selection_blockers(config: dict[str, Any], state: dict[str, Any], quality_status: str | None, gaps: list[str]) -> list[str]:
    blockers: list[str] = []
    discovery = discovery_config(config)

    if quality_status == "insufficient":
        blockers.append("Project data quality is insufficient for goal selection.")
        blockers.extend(f"Data gap: {gap}" for gap in gaps if str(gap).strip())

    if discovery.get("require_research_before_goal_selection", False):
        review_state = state.get("review_state", {})
        research_gate = review_state.get("research_gate", {}) if isinstance(review_state, dict) else {}
        if isinstance(research_gate, dict) and str(research_gate.get("status", "")).strip() == "need_more_context":
            summary = str(research_gate.get("summary", "")).strip()
            if summary:
                blockers.append(f"Research gate: {summary}")
            else:
                blockers.append("Research gate requires more context before selecting a goal.")
            open_gaps = research_gate.get("open_gaps", [])
            if isinstance(open_gaps, list):
                blockers.extend(f"Research gap: {gap}" for gap in open_gaps if str(gap).strip())

    return blockers


def current_evaluation_result(state: dict[str, Any]) -> str:
    review_state = state.get("review_state", {})
    if not isinstance(review_state, dict):
        return ""
    evaluation = review_state.get("evaluation", {})
    if not isinstance(evaluation, dict):
        return ""
    return str(evaluation.get("result", "")).strip()


def consecutive_review_blocks(state: dict[str, Any]) -> int:
    total = 0
    session_id = session_summary(state).get("id")
    current = current_evaluation_result(state)
    if current in {"revise", "fail"}:
        total += 1
    for item in reversed(state.get("history", [])):
        if not isinstance(item, dict):
            break
        item_session_id = str(item.get("session_id", "")).strip()
        if session_id and item_session_id != session_id:
            continue
        result = str(item.get("evaluation_result", "")).strip()
        if result in {"revise", "fail"}:
            total += 1
            continue
        if result:
            break
        break
    return total


def consecutive_goal_churn(state: dict[str, Any]) -> int:
    goal = state.get("current_goal")
    current = goal_title(goal).strip()
    if not current or current == "unspecified goal":
        return 0
    total = 0
    session_id = session_summary(state).get("id")
    for item in reversed(state.get("history", [])):
        if not isinstance(item, dict):
            break
        item_session_id = str(item.get("session_id", "")).strip()
        if session_id and item_session_id != session_id:
            continue
        if str(item.get("goal", "")).strip() == current:
            total += 1
            continue
        break
    return total


def assess_escalation(config: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    committee = committee_config(config)
    policy = committee.get("escalation_policy", {})
    if not isinstance(policy, dict):
        policy = {}

    review_limit = int(policy.get("repeat_evaluator_revise_or_fail", 2) or 2)
    validation_limit = int(policy.get("repeat_validation_failures", 2) or 2)
    churn_limit = int(policy.get("repeat_goal_churn", 2) or 2)

    review_blocks = consecutive_review_blocks(state)
    validation_failures = int(state.get("consecutive_failures", 0) or 0)
    goal_churn = consecutive_goal_churn(state)

    if validation_failures >= validation_limit:
        return {
            "status": "escalated",
            "reason": f"Validation has failed {validation_failures} time(s) in a row, meeting the escalation threshold of {validation_limit}.",
            "recommended_action": "Stop the loop, investigate the failing validation root cause, and narrow or replace the current goal before continuing.",
        }
    if review_blocks >= review_limit:
        return {
            "status": "escalated",
            "reason": f"Evaluator review has produced revise/fail {review_blocks} time(s) in a row, meeting the escalation threshold of {review_limit}.",
            "recommended_action": "Stop implementation planning, gather missing evidence, and revise the scope decision before continuing.",
        }
    if goal_churn >= churn_limit:
        return {
            "status": "escalated",
            "reason": f"The same goal has recurred across {goal_churn} recent published iteration(s), meeting the churn threshold of {churn_limit}.",
            "recommended_action": "Stop and reassess whether the current goal should be split, reframed, or deprioritized.",
        }
    if validation_failures == max(validation_limit - 1, 0) and validation_failures > 0:
        return {
            "status": "watch",
            "reason": f"Validation has failed {validation_failures} time(s) in a row and is one failure away from escalation.",
            "recommended_action": "Tighten the current scope and confirm the validation path before another implementation pass.",
        }
    if review_blocks == max(review_limit - 1, 0) and review_blocks > 0:
        return {
            "status": "watch",
            "reason": f"Evaluator review has produced revise/fail {review_blocks} time(s) in a row and is one step away from escalation.",
            "recommended_action": "Address the evaluator critique before continuing with implementation planning.",
        }
    if goal_churn == max(churn_limit - 1, 0) and goal_churn > 0:
        return {
            "status": "watch",
            "reason": f"The same goal has already recurred across {goal_churn} recent published iteration(s) and is one repeat away from escalation.",
            "recommended_action": "Confirm that the current goal is still the smallest high-value next step before continuing.",
        }
    return {
        "status": "not_needed",
        "reason": "",
        "recommended_action": "",
    }


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
