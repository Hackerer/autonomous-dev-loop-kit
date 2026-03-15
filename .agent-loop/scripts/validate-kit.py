#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

from common import validate_committee


ROOT = Path(__file__).resolve().parents[2]


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"[PASS] {message}")
    else:
        print(f"[FAIL] {message}")
        failures.append(message)


def is_positive_int(value: object) -> bool:
    return isinstance(value, int) and value > 0


def validate_json(path: Path, failures: list[str]) -> None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        print(f"[PASS] JSON parse: {path.relative_to(ROOT)}")
    except Exception as exc:  # pragma: no cover - defensive validation path
        print(f"[FAIL] JSON parse: {path.relative_to(ROOT)} -> {exc}")
        failures.append(f"JSON parse failed for {path.relative_to(ROOT)}")


def validate_python(path: Path, failures: list[str]) -> None:
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"[PASS] Python compile: {path.relative_to(ROOT)}")
    except py_compile.PyCompileError as exc:
        print(f"[FAIL] Python compile: {path.relative_to(ROOT)} -> {exc.msg}")
        failures.append(f"Python compile failed for {path.relative_to(ROOT)}")


def validate_skill(skill_md: Path, failures: list[str]) -> None:
    content = skill_md.read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    check(frontmatter is not None, f"Frontmatter exists: {skill_md.relative_to(ROOT)}", failures)
    if frontmatter is None:
        return

    body = frontmatter.group(1)
    check(re.search(r"^name:\s+[a-z0-9-]+$", body, re.MULTILINE) is not None, f"Skill name present: {skill_md.relative_to(ROOT)}", failures)
    check(re.search(r"^description:\s+.+$", body, re.MULTILINE) is not None, f"Skill description present: {skill_md.relative_to(ROOT)}", failures)


def main() -> int:
    failures: list[str] = []

    required_files = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "PLANS.md",
        ROOT / ".agents/skills/autonomous-dev-loop/SKILL.md",
        ROOT / ".claude/skills/autonomous-dev-loop/SKILL.md",
        ROOT / ".agent-loop/config.json",
        ROOT / ".agent-loop/state.json",
        ROOT / ".agent-loop/backlog.json",
        ROOT / ".agent-loop/references/protocol.md",
        ROOT / ".agent-loop/references/prompting-guidelines.md",
        ROOT / ".agent-loop/references/react-reasoning-acting.md",
        ROOT / ".agent-loop/references/data-quality-acquisition.md",
        ROOT / ".agent-loop/references/committee-driven-delivery.md",
        ROOT / ".agent-loop/references/example-data-acquisition-workflow.md",
        ROOT / ".agent-loop/templates/project-data-template.json",
        ROOT / ".agent-loop/templates/report-template.md",
    ]
    for path in required_files:
        check(path.exists(), f"Required file exists: {path.relative_to(ROOT)}", failures)

    for json_file in [
        ROOT / ".agent-loop/config.json",
        ROOT / ".agent-loop/state.json",
        ROOT / ".agent-loop/backlog.json",
        ROOT / ".agent-loop/templates/project-data-template.json",
    ]:
        validate_json(json_file, failures)

    for script in sorted((ROOT / ".agent-loop/scripts").glob("*.py")):
        validate_python(script, failures)

    validate_skill(ROOT / ".agents/skills/autonomous-dev-loop/SKILL.md", failures)
    validate_skill(ROOT / ".claude/skills/autonomous-dev-loop/SKILL.md", failures)

    config = json.loads((ROOT / ".agent-loop/config.json").read_text(encoding="utf-8"))
    validation_commands = config.get("validation", {}).get("commands", [])
    check(
        any(".agent-loop/scripts/validate-kit.py" in item.get("command", "") for item in validation_commands),
        "Validation uses validate-kit.py",
        failures,
    )
    check(
        is_positive_int(config.get("planning", {}).get("max_iterations_per_session")),
        "Planning max_iterations_per_session is a positive integer",
        failures,
    )
    committee_errors = validate_committee(config)
    check(not committee_errors, "Committee config is valid", failures)
    if committee_errors:
        for message in committee_errors:
            print(f"[FAIL] Committee config detail: {message}")
            failures.append(message)
    discovery = config.get("discovery", {})
    check(
        discovery.get("require_research_before_goal_selection") is True,
        "Discovery requires research before goal selection",
        failures,
    )
    check(
        discovery.get("require_committee_review") is True,
        "Discovery requires committee review",
        failures,
    )
    check(
        discovery.get("require_post_validation_reflection") is True,
        "Discovery requires post-validation reflection",
        failures,
    )

    generated_project_data = ROOT / ".agent-loop/data/project-data.generated.json"
    collector = subprocess.run(
        ["python3", ".agent-loop/scripts/collect-project-data.py", "--output", str(generated_project_data), "--no-state"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    check(collector.returncode == 0, "collect-project-data.py runs successfully", failures)
    if collector.returncode == 0:
        validate_json(generated_project_data, failures)

    generated_quality = ROOT / ".agent-loop/data/data-quality.generated.json"
    scorer = subprocess.run(
        [
            "python3",
            ".agent-loop/scripts/score-data-quality.py",
            "--input",
            str(generated_project_data),
            "--output",
            str(generated_quality),
            "--no-state",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    check(scorer.returncode == 0, "score-data-quality.py runs successfully", failures)
    if scorer.returncode == 0:
        validate_json(generated_quality, failures)

    committee_renderer = subprocess.run(
        ["python3", ".agent-loop/scripts/render-committee.py", "--json"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    check(committee_renderer.returncode == 0, "render-committee.py runs successfully", failures)

    review_capture = subprocess.run(
        [
            "python3",
            ".agent-loop/scripts/capture-review.py",
            "--research",
            "Sample repo scan",
            "--committee-feedback",
            "Sample committee feedback",
            "--decision",
            "Sample scope decision",
            "--json",
            "--no-state",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    check(review_capture.returncode == 0, "capture-review.py runs successfully", failures)

    if failures:
        print(f"\nValidation failed with {len(failures)} issue(s).", file=sys.stderr)
        return 1

    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
