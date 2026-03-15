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
    load_config,
    persona_catalog,
    secretariat_summary,
    validate_committee,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the committee-driven research and review model for this loop.")
    parser.add_argument("--json", action="store_true", help="Print the committee brief as JSON.")
    args = parser.parse_args()

    root = find_repo_root()
    config = load_config(root)
    errors = validate_committee(config)
    if errors:
        raise LoopError("Invalid committee config:\n- " + "\n- ".join(errors))

    discovery = discovery_config(config)
    roles = committee_summary(config)
    councils = council_summary(config)
    secretariat = secretariat_summary(config)
    evaluator = evaluator_summary(config)
    payload = {
        "research_required": bool(discovery.get("require_research_before_goal_selection", False)),
        "minimum_research_inputs": int(discovery.get("minimum_research_inputs", 0) or 0),
        "committee_review_required": bool(discovery.get("require_committee_review", False)),
        "post_validation_reflection_required": bool(discovery.get("require_post_validation_reflection", False)),
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
                print(f"    - {persona['label']}: {persona['focus']} | outputs: {outputs}")
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
        print(f"  Outputs: {outputs}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
