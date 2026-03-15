#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    council_summary,
    LoopError,
    committee_summary,
    discovery_config,
    evaluator_summary,
    find_repo_root,
    goal_title,
    load_config,
    load_json,
    load_state,
    persona_catalog,
    release_summary,
    secretariat_summary,
    validate_committee,
)


def build_review_packet(root, state: dict) -> dict:
    goal = state.get("current_goal")
    release = release_summary(state)
    project_data = state.get("project_data", {})
    snapshot_path = project_data.get("snapshot_path")
    quality_path = project_data.get("quality_path")
    snapshot = {}
    quality = {}
    if snapshot_path:
        snapshot_file = root / snapshot_path
        if snapshot_file.exists():
            snapshot = load_json(snapshot_file, default={})
    if quality_path:
        quality_file = root / quality_path
        if quality_file.exists():
            quality = load_json(quality_file, default={})

    repo = snapshot.get("repo", {}) if isinstance(snapshot, dict) else {}
    project = snapshot.get("project", {}) if isinstance(snapshot, dict) else {}
    product_context = snapshot.get("product_context", {}) if isinstance(snapshot, dict) else {}
    evidence = snapshot.get("evidence", {}) if isinstance(snapshot, dict) else {}
    latest_review_state = snapshot.get("latest_review_state", {}) if isinstance(snapshot, dict) else {}
    history = state.get("history", [])
    recent_iteration = history[-1] if isinstance(history, list) and history else {}

    return {
        "active_goal": {
            "id": goal.get("id") if isinstance(goal, dict) else None,
            "title": goal_title(goal) if goal else "",
            "priority": goal.get("priority") if isinstance(goal, dict) else None,
        },
        "active_release": {
            "number": release.get("number"),
            "title": release.get("title", ""),
            "summary": release.get("summary", ""),
            "goal_titles": list(release.get("goal_titles", [])),
            "brief": release.get("brief", {}),
            "status": release.get("status", "not_planned"),
        },
        "project_context": {
            "target_outcome": str(product_context.get("target_outcome", "")),
            "constraints": list(product_context.get("constraints", [])) if isinstance(product_context.get("constraints"), list) else [],
            "open_risks": list(product_context.get("open_risks", [])) if isinstance(product_context.get("open_risks"), list) else [],
            "current_branch": str(repo.get("current_branch", "")),
            "repo_archetype": str(project.get("repo_archetype", "")),
            "archetype_profile": project.get("archetype_profile", {}) if isinstance(project.get("archetype_profile"), dict) else {},
        },
        "quality_context": {
            "status": project_data.get("last_quality_status"),
            "score": project_data.get("last_quality_score"),
            "blocking_gaps": list(quality.get("blocking_gaps", [])) if isinstance(quality.get("blocking_gaps"), list) else [],
            "missing_signals": list(quality.get("missing_signals", [])) if isinstance(quality.get("missing_signals"), list) else [],
            "recommendations": list(quality.get("recommendations", [])) if isinstance(quality.get("recommendations"), list) else [],
        },
        "evidence_context": {
            "confidence": str(evidence.get("confidence", "")),
            "freshness": str(evidence.get("freshness", "")),
            "sources": list(evidence.get("sources", [])) if isinstance(evidence.get("sources"), list) else [],
        },
        "review_context": {
            "matches_active_goal": latest_review_state.get("matches_current_goal"),
            "research_status": latest_review_state.get("research_gate", {}).get("status")
            if isinstance(latest_review_state.get("research_gate"), dict)
            else "not_started",
            "open_gaps": list(latest_review_state.get("research_gate", {}).get("open_gaps", []))
            if isinstance(latest_review_state.get("research_gate"), dict)
            else [],
        },
        "recent_iteration": recent_iteration if isinstance(recent_iteration, dict) else {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the committee-driven research and review model for this loop.")
    parser.add_argument("--json", action="store_true", help="Print the committee brief as JSON.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    state = load_state(root)
    errors = validate_committee(config)
    if errors:
        raise LoopError("Invalid committee config:\n- " + "\n- ".join(errors))

    discovery = discovery_config(config)
    roles = committee_summary(config)
    councils = council_summary(config)
    secretariat = secretariat_summary(config)
    evaluator = evaluator_summary(config)
    review_packet = build_review_packet(root, state)
    payload = {
        "research_required": bool(discovery.get("require_research_before_goal_selection", False)),
        "minimum_research_inputs": int(discovery.get("minimum_research_inputs", 0) or 0),
        "committee_review_required": bool(discovery.get("require_committee_review", False)),
        "post_validation_reflection_required": bool(discovery.get("require_post_validation_reflection", False)),
        "review_packet": review_packet,
        "persona_catalog": list(persona_catalog(config).values()),
        "councils": councils,
        "secretariat": secretariat,
        "evaluator": evaluator,
        "roles": roles,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    print("Committee-driven execution model")
    print(
        f"- Research before goal selection: {'required' if payload['research_required'] else 'optional'}"
        f" (minimum inputs: {payload['minimum_research_inputs']})"
    )
    print(f"- Committee review before implementation: {'required' if payload['committee_review_required'] else 'optional'}")
    print(
        f"- Reflection after validation: {'required' if payload['post_validation_reflection_required'] else 'optional'}"
    )
    active_goal = review_packet.get("active_goal", {})
    active_release = review_packet.get("active_release", {})
    print(f"- Active goal: {active_goal.get('title') or 'no active goal selected'}")
    if active_release.get("number") is not None:
        print(f"- Active release: R{active_release.get('number')} {active_release.get('title')}")
        brief = active_release.get("brief", {})
        if isinstance(brief, dict):
            objective = str(brief.get("objective", "")).strip()
            if objective:
                print(f"- Release objective: {objective}")
            target_user_value = str(brief.get("target_user_value", "")).strip()
            if target_user_value:
                print(f"- Target user value: {target_user_value}")
            packaging_rationale = str(brief.get("packaging_rationale", "")).strip()
            if packaging_rationale:
                print(f"- Packaging rationale: {packaging_rationale}")
    project_context = review_packet.get("project_context", {})
    print(f"- Current branch: {project_context.get('current_branch') or 'unknown'}")
    print(f"- Repo archetype: {project_context.get('repo_archetype') or 'unknown'}")
    archetype_profile = project_context.get("archetype_profile", {})
    if isinstance(archetype_profile, dict) and archetype_profile.get("label"):
        print(f"- Archetype profile: {archetype_profile.get('label')} ({archetype_profile.get('id')})")
    quality_context = review_packet.get("quality_context", {})
    print(
        f"- Quality status: {quality_context.get('status') or 'unknown'}"
        + (
            f", score {quality_context.get('score')}"
            if quality_context.get("score") is not None
            else ""
        )
    )
    missing_signals = quality_context.get("missing_signals", [])
    if missing_signals:
        print(f"- Missing quality signals: {', '.join(missing_signals)}")
    blocking_gaps = quality_context.get("blocking_gaps", [])
    if blocking_gaps:
        print("- Blocking gaps:")
        for gap in blocking_gaps:
            print(f"  - {gap}")
    recent_iteration = review_packet.get("recent_iteration", {})
    if isinstance(recent_iteration, dict) and recent_iteration.get("iteration"):
        print(
            f"- Recent iteration: v{recent_iteration.get('iteration')} "
            f"{recent_iteration.get('goal', '')}".rstrip()
        )
    review_context = review_packet.get("review_context", {})
    open_gaps = review_context.get("open_gaps", [])
    if open_gaps:
        print("- Research open gaps:")
        for gap in open_gaps:
            print(f"  - {gap}")
    for role in roles:
        members = ", ".join(role["members"]) if role["members"] else "no members configured"
        print(f"- {role['label']} ({role['member_count']} members): {role['responsibility']}")
        print(f"  Members: {members}")
    if councils:
        print("- V2 council brief:")
        for council in councils:
            print(f"  - {council['label']}: {council['responsibility']}")
            for persona in council["personas"]:
                outputs = ", ".join(persona["output_fields"]) if persona["output_fields"] else "no output fields configured"
                release_outputs = persona.get("release_output_fields", [])
                release_output_text = ""
                if release_outputs:
                    release_output_text = f" | release outputs: {', '.join(release_outputs)}"
                print(f"    - {persona['label']}: {persona['focus']} | outputs: {outputs}{release_output_text}")
    if secretariat:
        print("- Secretariat:")
        for persona in secretariat:
            outputs = ", ".join(persona["output_fields"]) if persona["output_fields"] else "no output fields configured"
            print(f"  - {persona['label']}: {persona['responsibility']} | outputs: {outputs}")
    if evaluator:
        persona = evaluator.get("persona", {})
        outputs = ", ".join(persona.get("output_fields", [])) if persona else "no output fields configured"
        print(f"- Evaluator: {persona.get('label', 'unconfigured evaluator')}")
        print(f"  Rubric: {evaluator.get('rubric_ref', '')}")
        print(f"  Implementation gate mode: {evaluator.get('implementation_gate_mode', 'blocking')}")
        print(f"  Outputs: {outputs}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
