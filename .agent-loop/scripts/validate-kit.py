#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
import tempfile
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


def install_target_project(target: Path, args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/install-into-project.sh", "--target", str(target), *(args or [])],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def seeded_state(goal_id: str) -> dict:
    return {
        "iteration": 0,
        "status": "goal_selected",
        "session": {
            "status": "active",
            "target_iterations": 1,
            "completed_iterations": 0,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": None,
        },
        "project_data": {
            "snapshot_path": None,
            "quality_path": None,
            "last_collected_at": None,
            "last_quality_score": None,
            "last_quality_status": None,
        },
        "current_goal": {
            "id": goal_id,
            "title": "Gate review-state reporting and publication",
            "selected_at": "2026-03-15T00:00:00Z",
            "source": ".agent-loop/backlog.json",
        },
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
        "last_validation": {
            "status": "passed",
            "ran_at": "2026-03-15T00:00:00Z",
            "results": [
                {
                    "command": "python3 .agent-loop/scripts/validate-kit.py",
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "name": "validate-kit",
                    "required": True,
                    "passed": True,
                }
            ],
        },
        "consecutive_failures": 0,
        "history": [],
    }


def validate_review_gate(failures: list[str]) -> None:
    goal_id = "review-gate-test"
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a validation target", failures)

        state_path = target / ".agent-loop/state.json"
        write_json(state_path, seeded_state(goal_id))

        report_attempt = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/write-report.py",
                "--analysis",
                "Gate test",
                "--acceptance",
                "Gate test",
                "--delivered",
                "Gate test",
                "--reflection",
                "Gate test",
                "--next-goal",
                "Gate test",
            ],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(report_attempt.returncode != 0, "write-report.py rejects missing review state when committee review is required", failures)
        check(
            "capture-review.py" in report_attempt.stderr or "review state" in report_attempt.stderr.lower(),
            "write-report.py explains how to satisfy the review-state gate",
            failures,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a publish-gate target", failures)

        git_init = subprocess.run(["git", "init"], cwd=str(target), text=True, capture_output=True, check=False)
        check(git_init.returncode == 0, "Publish-gate target initializes git", failures)
        subprocess.run(["git", "config", "user.name", "Kit Validator"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "validator@example.com"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/example/autonomous-dev-loop-kit.git"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )

        state = seeded_state(goal_id)
        state["draft_iteration"] = 1
        state["draft_report"] = "docs/reports/v1.md"
        state["draft_goal"] = state["current_goal"]
        write_json(target / ".agent-loop/state.json", state)
        (target / "docs/reports").mkdir(parents=True, exist_ok=True)
        (target / "docs/reports/v1.md").write_text("# Gate Test Report\n", encoding="utf-8")

        publish_attempt = subprocess.run(
            ["python3", ".agent-loop/scripts/publish-iteration.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(publish_attempt.returncode != 0, "publish-iteration.py rejects missing review state when committee review is required", failures)
        check(
            "capture-review.py" in publish_attempt.stderr or "review state" in publish_attempt.stderr.lower(),
            "publish-iteration.py explains how to satisfy the review-state gate",
            failures,
        )


def main() -> int:
    failures: list[str] = []

    required_files = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "PLANS.md",
        ROOT / "scripts/install-into-project.sh",
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
        project_data = json.loads(generated_project_data.read_text(encoding="utf-8"))
        check(isinstance(project_data.get("latest_review_state"), dict), "Project data includes latest_review_state", failures)

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

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        (target / ".agent-loop").mkdir(parents=True, exist_ok=True)
        preserved_config = {
            "validation": {
                "commands": [
                    {
                        "name": "custom-validation",
                        "command": "echo custom",
                        "required": True,
                    }
                ]
            }
        }
        (target / ".agent-loop/config.json").write_text(json.dumps(preserved_config), encoding="utf-8")
        installer = subprocess.run(
            ["bash", "scripts/install-into-project.sh", "--target", str(target)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        check(installer.returncode == 0, "install-into-project.sh runs successfully", failures)
        check((target / ".agents/skills/autonomous-dev-loop/SKILL.md").exists(), "Project installer syncs .agents skill", failures)
        check((target / ".claude/skills/autonomous-dev-loop/SKILL.md").exists(), "Project installer syncs .claude skill", failures)
        check((target / ".agent-loop/scripts/collect-project-data.py").exists(), "Project installer syncs loop scripts", failures)
        installed_config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        check(
            installed_config.get("validation", {}).get("commands", [{}])[0].get("command") == "echo custom",
            "Project installer preserves existing config by default",
            failures,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        (target / ".agent-loop").mkdir(parents=True, exist_ok=True)
        preserved_config = {
            "validation": {
                "commands": [
                    {
                        "name": "custom-validation",
                        "command": "echo custom",
                        "required": True,
                    }
                ]
            }
        }
        (target / ".agent-loop/config.json").write_text(json.dumps(preserved_config), encoding="utf-8")
        installer = subprocess.run(
            ["bash", "scripts/install-into-project.sh", "--target", str(target), "--overwrite-config"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        check(installer.returncode == 0, "Project installer supports --overwrite-config", failures)
        installed_config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        check(
            any(".agent-loop/scripts/validate-kit.py" in item.get("command", "") for item in installed_config.get("validation", {}).get("commands", [])),
            "Project installer can replace config when requested",
            failures,
        )

    validate_review_gate(failures)

    if failures:
        print(f"\nValidation failed with {len(failures)} issue(s).", file=sys.stderr)
        return 1

    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
