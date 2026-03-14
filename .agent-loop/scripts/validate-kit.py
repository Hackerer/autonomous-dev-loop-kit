#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"[PASS] {message}")
    else:
        print(f"[FAIL] {message}")
        failures.append(message)


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
        ROOT / ".agent-loop/templates/report-template.md",
    ]
    for path in required_files:
        check(path.exists(), f"Required file exists: {path.relative_to(ROOT)}", failures)

    for json_file in [
        ROOT / ".agent-loop/config.json",
        ROOT / ".agent-loop/state.json",
        ROOT / ".agent-loop/backlog.json",
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
        config.get("planning", {}).get("max_iterations_per_session") == 10,
        "Planning max_iterations_per_session is set to 10",
        failures,
    )

    if failures:
        print(f"\nValidation failed with {len(failures)} issue(s).", file=sys.stderr)
        return 1

    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
