#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import (
    LoopError,
    committee_summary,
    discovery_config,
    find_repo_root,
    load_config,
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
    payload = {
        "research_required": bool(discovery.get("require_research_before_goal_selection", False)),
        "minimum_research_inputs": int(discovery.get("minimum_research_inputs", 0) or 0),
        "committee_review_required": bool(discovery.get("require_committee_review", False)),
        "post_validation_reflection_required": bool(discovery.get("require_post_validation_reflection", False)),
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
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
