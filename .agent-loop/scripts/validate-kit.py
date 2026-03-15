#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from common import load_state, validate_committee


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


def seeded_state(goal_id: str, evaluator_result: str | None = None) -> dict:
    state = {
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
            "evaluation": {
                "status": "not_started",
                "rubric_version": "",
                "scores": {},
                "weighted_score": None,
                "result": "pending",
                "critique": [],
                "minimum_fixes_required": [],
            },
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
    if evaluator_result is not None:
        state["review_state"]["status"] = "captured"
        state["review_state"]["captured_at"] = "2026-03-15T00:00:00Z"
        state["review_state"]["research_findings"] = ["Seeded review finding"]
        state["review_state"]["committee_feedback"] = ["Seeded committee feedback"]
        state["review_state"]["committee_decision"] = ["Seeded committee decision"]
        state["review_state"]["goal_id"] = goal_id
        state["review_state"]["goal_title"] = "Gate review-state reporting and publication"
        state["review_state"]["evaluation"] = {
            "status": "captured",
            "rubric_version": "iteration-readiness-v1",
            "scores": {"goal_clarity": 4.5},
            "weighted_score": 4.5,
            "result": evaluator_result,
            "critique": [],
            "minimum_fixes_required": [],
        }
    return state


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


def validate_evaluator_gate(failures: list[str]) -> None:
    goal_id = "evaluator-gate-test"
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed an evaluator-gate target", failures)

        write_json(target / ".agent-loop/state.json", seeded_state(goal_id, evaluator_result="revise"))
        readiness_attempt = subprocess.run(
            ["python3", ".agent-loop/scripts/assert-implementation-readiness.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(readiness_attempt.returncode != 0, "assert-implementation-readiness.py rejects missing evaluator pass", failures)
        check(
            "evaluator" in readiness_attempt.stderr.lower() or "evaluation" in readiness_attempt.stderr.lower(),
            "assert-implementation-readiness.py explains the evaluator gate",
            failures,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a passing evaluator target", failures)

        write_json(target / ".agent-loop/state.json", seeded_state(goal_id, evaluator_result="pass"))
        readiness_attempt = subprocess.run(
            ["python3", ".agent-loop/scripts/assert-implementation-readiness.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(readiness_attempt.returncode == 0, "assert-implementation-readiness.py accepts matching evaluator pass", failures)

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed an advisory evaluator target", failures)

        config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        config["committee"]["evaluator"]["implementation_gate_mode"] = "advisory"
        write_json(target / ".agent-loop/config.json", config)
        write_json(target / ".agent-loop/state.json", seeded_state(goal_id, evaluator_result="revise"))
        readiness_attempt = subprocess.run(
            ["python3", ".agent-loop/scripts/assert-implementation-readiness.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(readiness_attempt.returncode == 0, "assert-implementation-readiness.py allows advisory evaluator mode", failures)
        check(
            "advisory warning" in readiness_attempt.stdout.lower(),
            "assert-implementation-readiness.py reports advisory evaluator mode clearly",
            failures,
        )


def validate_structured_committee_flow(failures: list[str]) -> None:
    goal_id = "structured-committee-flow"
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a structured-flow target", failures)

        git_init = subprocess.run(["git", "init"], cwd=str(target), text=True, capture_output=True, check=False)
        check(git_init.returncode == 0, "Structured-flow target initializes git", failures)
        subprocess.run(["git", "config", "user.name", "Kit Validator"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "validator@example.com"], cwd=str(target), text=True, capture_output=True, check=False)

        config_path = target / ".agent-loop/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["git"]["strategy"] = "commit-only"
        write_json(config_path, config)

        state = seeded_state(goal_id, evaluator_result="pass")
        state["current_goal"]["title"] = "Structured committee flow"
        state["review_state"]["goal_title"] = "Structured committee flow"
        state["review_state"]["research_gate"] = {
            "status": "captured",
            "summary": "Seeded research gate summary",
            "evidence_refs": ["PLANS.md"],
            "data_quality_score": 100,
            "open_gaps": [],
        }
        write_json(target / ".agent-loop/state.json", state)

        capture = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/capture-review.py",
                "--product-summary",
                "Seeded product council summary",
                "--selected-goal",
                "Structured committee flow",
                "--why-selected",
                "Seeded scope decision",
                "--scope-in",
                "Seeded scope in",
                "--stop-condition",
                "Seeded stop condition",
                "--required-validation",
                "Seeded validation",
                "--rubric-version",
                "iteration-readiness-v1",
                "--score",
                "goal_clarity=4.5",
                "--weighted-score",
                "4.5",
                "--evaluation-result",
                "pass",
                "--escalation-status",
                "watch",
                "--escalation-reason",
                "Seeded escalation reason",
                "--recommended-action",
                "Seeded escalation action",
                "--delivery-summary",
                "Seeded delivery secretary summary",
                "--delivery-next-action",
                "Seeded delivery secretary next action",
                "--audit-summary",
                "Seeded audit secretary summary",
                "--decision-record",
                "Seeded audit decision record",
                "--audit-open-gap",
                "Seeded audit gap",
            ],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(capture.returncode == 0, "Structured-flow target captures committee review", failures)

        readiness = subprocess.run(
            ["python3", ".agent-loop/scripts/assert-implementation-readiness.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(readiness.returncode == 0, "Structured-flow target passes implementation readiness", failures)

        report = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/write-report.py",
                "--analysis",
                "Seeded structured flow analysis",
                "--acceptance",
                "Seeded structured flow acceptance",
                "--delivered",
                "Seeded structured flow delivery",
                "--reflection",
                "Seeded structured flow reflection",
                "--next-goal",
                "Seeded structured flow next goal",
            ],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(report.returncode == 0, "Structured-flow target writes a report", failures)
        report_content = (target / "docs/reports/v1.md").read_text(encoding="utf-8")
        check("Seeded stop condition" in report_content, "Structured-flow report renders stop conditions", failures)
        check("Seeded escalation reason" in report_content, "Structured-flow report renders escalation reasons", failures)
        check("Seeded delivery secretary summary" in report_content, "Structured-flow report renders delivery secretary output", failures)
        check("Seeded audit decision record" in report_content, "Structured-flow report renders audit secretary output", failures)
        check("Implementation gate:" in report_content, "Structured-flow report renders implementation gate outcome", failures)

        publish = subprocess.run(
            ["python3", ".agent-loop/scripts/publish-iteration.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(publish.returncode == 0, "Structured-flow target publishes with commit-only", failures)


def validate_goal_selection_readiness(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a goal-selection quality target", failures)

        quality_path = target / ".agent-loop/data/data-quality.json"
        write_json(
            quality_path,
            {
                "snapshot_path": ".agent-loop/data/project-data.json",
                "overall_score": 45,
                "status": "insufficient",
                "blocking_gaps": ["missing validation commands", "missing target outcome"],
                "recommendations": [],
            },
        )
        state = load_state(target)
        state["session"] = {
            "status": "active",
            "target_iterations": 1,
            "completed_iterations": 0,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": None,
        }
        state["project_data"]["quality_path"] = ".agent-loop/data/data-quality.json"
        state["project_data"]["last_quality_score"] = 45
        state["project_data"]["last_quality_status"] = "insufficient"
        write_json(target / ".agent-loop/state.json", state)

        blocked = subprocess.run(
            ["python3", ".agent-loop/scripts/select-next-goal.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(blocked.returncode != 0, "select-next-goal.py blocks when project-data quality is insufficient", failures)
        check(
            "missing validation commands" in blocked.stderr and "missing target outcome" in blocked.stderr,
            "select-next-goal.py reports blocking data gaps clearly",
            failures,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a goal-selection research target", failures)

        state = load_state(target)
        state["session"] = {
            "status": "active",
            "target_iterations": 1,
            "completed_iterations": 0,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": None,
        }
        state["review_state"]["status"] = "captured"
        state["review_state"]["captured_at"] = "2026-03-15T00:00:00Z"
        state["review_state"]["research_gate"] = {
            "status": "need_more_context",
            "summary": "More repo evidence is required before scope selection.",
            "evidence_refs": [],
            "data_quality_score": 100,
            "open_gaps": ["inspect target installer behavior", "confirm evaluator output contract"],
        }
        write_json(target / ".agent-loop/state.json", state)

        blocked = subprocess.run(
            ["python3", ".agent-loop/scripts/select-next-goal.py"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(blocked.returncode != 0, "select-next-goal.py blocks when research gate requires more context", failures)
        check(
            "inspect target installer behavior" in blocked.stderr and "confirm evaluator output contract" in blocked.stderr,
            "select-next-goal.py reports research gaps clearly",
            failures,
        )


def validate_evaluator_brief(failures: list[str]) -> None:
    goal_id = "evaluator-brief-test"
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed an evaluator-brief target", failures)

        snapshot_path = target / ".agent-loop/data/project-data.json"
        write_json(
            snapshot_path,
            {
                "repo": {"current_branch": "main"},
                "product_context": {
                    "target_outcome": "Ship one small evaluator-facing improvement",
                    "constraints": ["keep the brief independent from committee debate"],
                },
                "validation": {
                    "configured_commands": ["python3 .agent-loop/scripts/validate-kit.py"],
                },
            },
        )

        state = seeded_state(goal_id)
        state["project_data"]["snapshot_path"] = ".agent-loop/data/project-data.json"
        state["project_data"]["last_quality_status"] = "ready"
        state["review_state"]["status"] = "captured"
        state["review_state"]["captured_at"] = "2026-03-15T00:00:00Z"
        state["review_state"]["research_findings"] = ["Seeded evaluator-brief research"]
        state["review_state"]["goal_id"] = goal_id
        state["review_state"]["goal_title"] = "Gate review-state reporting and publication"
        state["review_state"]["scope_decision"] = {
            "status": "captured",
            "selected_goal": "Render evaluator input contract",
            "why_selected": "Make the evaluator lane directly usable.",
            "scope_in": ["render goal, scope, rubric, and project context"],
            "scope_out": ["do not include committee debate"],
            "assumptions": ["scope decision already exists"],
            "risks": ["brief could accidentally leak committee detail"],
            "required_validation": ["python3 .agent-loop/scripts/validate-kit.py"],
            "stop_conditions": ["stop if committee discussion appears in the brief"],
            "dissent": [],
            "next_action": "render the evaluator brief",
        }
        write_json(target / ".agent-loop/state.json", state)

        brief = subprocess.run(
            ["python3", ".agent-loop/scripts/render-evaluator-brief.py", "--json"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(brief.returncode == 0, "render-evaluator-brief.py runs successfully", failures)
        if brief.returncode == 0:
            payload = json.loads(brief.stdout)
            check(
                payload.get("scope_decision", {}).get("selected_goal") == "Render evaluator input contract",
                "render-evaluator-brief.py exposes the selected scope decision",
                failures,
            )
            check(
                payload.get("rubric", {}).get("id") == "iteration-readiness-v1",
                "render-evaluator-brief.py includes the evaluator rubric",
                failures,
            )
            check(isinstance(payload.get("implementation_gate"), dict), "render-evaluator-brief.py exposes implementation gate status", failures)
            check(
                "committee_feedback" not in payload and "councils" not in payload,
                "render-evaluator-brief.py stays independent from council discussion details",
                failures,
            )


def validate_escalation_policy(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed an escalation-policy target", failures)

        state = load_state(target)
        state["consecutive_failures"] = 2
        write_json(target / ".agent-loop/state.json", state)

        assessment = subprocess.run(
            ["python3", ".agent-loop/scripts/assess-escalation.py", "--json"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(assessment.returncode == 0, "assess-escalation.py runs successfully", failures)
        if assessment.returncode == 0:
            payload = json.loads(assessment.stdout)
            check(payload.get("status") == "escalated", "assess-escalation.py escalates repeated validation failures", failures)

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a review-escalation target", failures)

        state = seeded_state("review-escalation-test")
        state["history"] = [
            {
                "iteration": 1,
                "goal": "Review escalation test",
                "evaluation_result": "revise",
                "validation_status": "passed",
            }
        ]
        state["review_state"]["status"] = "captured"
        state["review_state"]["goal_id"] = "review-escalation-test"
        state["review_state"]["goal_title"] = "Gate review-state reporting and publication"
        state["review_state"]["evaluation"] = {
            "status": "captured",
            "rubric_version": "iteration-readiness-v1",
            "scores": {"goal_clarity": 3.0},
            "weighted_score": 3.0,
            "result": "revise",
            "critique": [],
            "minimum_fixes_required": [],
        }
        write_json(target / ".agent-loop/state.json", state)

        assessment = subprocess.run(
            ["python3", ".agent-loop/scripts/assess-escalation.py", "--apply", "--json"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(assessment.returncode == 0, "assess-escalation.py can persist escalation results", failures)
        if assessment.returncode == 0:
            payload = json.loads(assessment.stdout)
            check(payload.get("status") == "escalated", "assess-escalation.py escalates repeated evaluator revise/fail results", failures)
            updated_state = load_state(target)
            check(
                updated_state.get("review_state", {}).get("escalation", {}).get("status") == "escalated",
                "assess-escalation.py persists escalation into review_state",
                failures,
            )


def validate_review_reset_on_goal_change(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a review-reset target", failures)

        state = load_state(target)
        state["session"] = {
            "status": "active",
            "target_iterations": 2,
            "completed_iterations": 0,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": None,
        }
        state["current_goal"] = {
            "id": "goal-a",
            "title": "First goal",
            "selected_at": "2026-03-15T00:00:00Z",
            "source": ".agent-loop/backlog.json",
        }
        write_json(target / ".agent-loop/state.json", state)

        first_capture = subprocess.run(
            ["python3", ".agent-loop/scripts/capture-review.py", "--research", "First goal finding"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(first_capture.returncode == 0, "capture-review.py records the first goal review state", failures)

        state = load_state(target)
        state["current_goal"] = {
            "id": "goal-b",
            "title": "Second goal",
            "selected_at": "2026-03-15T00:01:00Z",
            "source": ".agent-loop/backlog.json",
        }
        write_json(target / ".agent-loop/state.json", state)

        second_capture = subprocess.run(
            ["python3", ".agent-loop/scripts/capture-review.py", "--research", "Second goal finding"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(second_capture.returncode == 0, "capture-review.py records the second goal review state", failures)
        if second_capture.returncode == 0:
            updated_state = load_state(target)
            findings = updated_state.get("review_state", {}).get("research_findings", [])
            check("Second goal finding" in findings, "capture-review.py keeps the new goal finding", failures)
            check("First goal finding" not in findings, "capture-review.py resets review state when the goal changes", failures)


def validate_session_continuation(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a session-continuation target", failures)

        state = load_state(target)
        state["session"] = {
            "status": "completed",
            "target_iterations": 2,
            "completed_iterations": 2,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": "2026-03-15T00:10:00Z",
        }
        state["status"] = "session_completed"
        write_json(target / ".agent-loop/state.json", state)

        continued = subprocess.run(
            ["python3", ".agent-loop/scripts/continue-loop-session.py", "--add", "3"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(continued.returncode == 0, "continue-loop-session.py extends a completed session", failures)
        if continued.returncode == 0:
            updated_state = load_state(target)
            check(updated_state.get("session", {}).get("target_iterations") == 5, "continue-loop-session.py preserves completed progress while extending target", failures)
            check(updated_state.get("session", {}).get("status") == "active", "continue-loop-session.py reopens the session as active", failures)


def main() -> int:
    failures: list[str] = []

    required_files = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "PLANS.md",
        ROOT / "scripts/install-into-project.sh",
        ROOT / ".agent-loop/scripts/assert-implementation-readiness.py",
        ROOT / ".agent-loop/scripts/assess-escalation.py",
        ROOT / ".agent-loop/scripts/continue-loop-session.py",
        ROOT / ".agent-loop/scripts/render-evaluator-brief.py",
        ROOT / ".agent-loop/scripts/score-evaluator-readiness.py",
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
        ROOT / ".agent-loop/references/iteration-readiness-rubric.json",
        ROOT / ".agent-loop/templates/project-data-template.json",
        ROOT / ".agent-loop/templates/report-template.md",
    ]
    for path in required_files:
        check(path.exists(), f"Required file exists: {path.relative_to(ROOT)}", failures)

    for json_file in [
        ROOT / ".agent-loop/config.json",
        ROOT / ".agent-loop/state.json",
        ROOT / ".agent-loop/backlog.json",
        ROOT / ".agent-loop/references/iteration-readiness-rubric.json",
        ROOT / ".agent-loop/templates/project-data-template.json",
    ]:
        validate_json(json_file, failures)

    for script in sorted((ROOT / ".agent-loop/scripts").glob("*.py")):
        validate_python(script, failures)

    validate_skill(ROOT / ".agents/skills/autonomous-dev-loop/SKILL.md", failures)
    validate_skill(ROOT / ".claude/skills/autonomous-dev-loop/SKILL.md", failures)

    config = json.loads((ROOT / ".agent-loop/config.json").read_text(encoding="utf-8"))
    state = load_state(ROOT)
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
    archetype_profiles = discovery.get("archetype_profiles", {})
    check(isinstance(archetype_profiles, dict), "Discovery exposes archetype profile config", failures)
    check(
        archetype_profiles.get("default_profile") == "baseline",
        "Archetype profiles define the baseline default profile",
        failures,
    )
    profiles = archetype_profiles.get("profiles", {})
    check(isinstance(profiles, dict) and "agent-skill-kit" in profiles, "Archetype profiles include an agent-skill-kit profile", failures)
    evaluator = config.get("committee", {}).get("evaluator", {})
    rubric_ref = evaluator.get("rubric_ref")
    check(rubric_ref == ".agent-loop/references/iteration-readiness-rubric.json", "Config points to the committed evaluator rubric", failures)
    check(evaluator.get("implementation_gate_mode") == "blocking", "Evaluator defaults to blocking implementation gate mode", failures)
    rubric = json.loads((ROOT / ".agent-loop/references/iteration-readiness-rubric.json").read_text(encoding="utf-8"))
    check(rubric.get("id") == "iteration-readiness-v1", "Evaluator rubric id is correct", failures)
    check(isinstance(rubric.get("criteria"), dict) and len(rubric.get("criteria", {})) >= 6, "Evaluator rubric exposes weighted criteria", failures)
    review_state = state.get("review_state", {})
    check(isinstance(review_state.get("research_gate"), dict), "State normalization exposes research_gate", failures)
    check(isinstance(review_state.get("councils"), dict), "State normalization exposes council summaries", failures)
    check(isinstance(review_state.get("secretariat"), dict), "State normalization exposes secretariat summaries", failures)
    check(isinstance(review_state.get("scope_decision"), dict), "State normalization exposes scope_decision", failures)
    check(isinstance(review_state.get("evaluation"), dict), "State normalization exposes evaluation", failures)
    check(isinstance(review_state.get("escalation"), dict), "State normalization exposes escalation", failures)

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
        latest_review_state = project_data.get("latest_review_state", {})
        check(isinstance(latest_review_state.get("evaluation"), dict), "Project data includes evaluation readiness summary", failures)
        check(isinstance(latest_review_state.get("scope_decision"), dict), "Project data includes scope decision summary", failures)
        check(isinstance(latest_review_state.get("secretariat"), dict), "Project data includes secretariat summary", failures)
        archetype_profile = project_data.get("project", {}).get("archetype_profile", {})
        check(isinstance(archetype_profile, dict), "Project data includes an archetype profile summary", failures)
        check(
            archetype_profile.get("id") == "agent-skill-kit",
            "Project data resolves the current repo archetype profile",
            failures,
        )

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
        quality = json.loads(generated_quality.read_text(encoding="utf-8"))
        check(isinstance(quality.get("archetype_profile"), dict), "score-data-quality.py records the active archetype profile", failures)
        check(
            quality.get("archetype_profile", {}).get("id") == "agent-skill-kit",
            "score-data-quality.py uses the current repo archetype profile",
            failures,
        )
        check(isinstance(quality.get("evaluated_signals"), list) and quality.get("evaluated_signals"), "score-data-quality.py records evaluated signal details", failures)
        check(
            "repo_archetype" in quality.get("archetype_profile", {}).get("required_signals", []),
            "agent-skill-kit profile requires repo_archetype during scoring",
            failures,
        )

    committee_renderer = subprocess.run(
        ["python3", ".agent-loop/scripts/render-committee.py", "--json"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    check(committee_renderer.returncode == 0, "render-committee.py runs successfully", failures)
    if committee_renderer.returncode == 0:
        rendered = json.loads(committee_renderer.stdout)
        check(isinstance(rendered.get("councils"), list) and len(rendered.get("councils", [])) >= 3, "Committee renderer exposes council summaries", failures)
        check(isinstance(rendered.get("secretariat"), list) and len(rendered.get("secretariat", [])) >= 2, "Committee renderer exposes secretariat summaries", failures)
        check(isinstance(rendered.get("evaluator"), dict) and isinstance(rendered.get("evaluator", {}).get("persona"), dict), "Committee renderer exposes evaluator summary", failures)
        review_packet = rendered.get("review_packet", {})
        check(isinstance(review_packet, dict), "Committee renderer exposes a live review packet", failures)
        check(isinstance(review_packet.get("active_goal"), dict), "Committee renderer exposes the active goal context", failures)
        check(isinstance(review_packet.get("quality_context"), dict), "Committee renderer exposes quality context", failures)

    review_capture = subprocess.run(
        [
            "python3",
            ".agent-loop/scripts/capture-review.py",
            "--research",
            "Sample repo scan",
            "--research-status",
            "captured",
            "--research-summary",
            "Sample research summary",
            "--evidence-ref",
            "PLANS.md",
            "--quality-score",
            "100",
            "--open-gap",
            "No blocking gaps",
            "--committee-feedback",
            "Sample committee feedback",
            "--decision",
            "Sample scope decision",
            "--product-summary",
            "Sample product summary",
            "--product-decision",
            "Sample product decision",
            "--product-dissent",
            "Sample product dissent",
            "--architecture-summary",
            "Sample architecture summary",
            "--operator-summary",
            "Sample operator summary",
            "--delivery-summary",
            "Sample delivery secretary summary",
            "--delivery-next-action",
            "Sample delivery next action",
            "--audit-summary",
            "Sample audit secretary summary",
            "--decision-record",
            "Sample audit decision record",
            "--audit-evidence-ref",
            "README.md",
            "--audit-open-gap",
            "Sample audit gap",
            "--audit-dissent",
            "Sample audit dissent",
            "--selected-goal",
            "Sample selected goal",
            "--why-selected",
            "Sample why selected",
            "--scope-in",
            "Sample scope in",
            "--scope-out",
            "Sample scope out",
            "--assumption",
            "Sample assumption",
            "--risk",
            "Sample risk",
            "--required-validation",
            "Sample validation requirement",
            "--stop-condition",
            "Sample stop condition",
            "--scope-dissent",
            "Sample scope dissent",
            "--next-action",
            "Sample next action",
            "--rubric-version",
            "iteration-readiness-v1",
            "--score",
            "goal_clarity=4.5",
            "--score",
            "scope_fitness=4.0",
            "--weighted-score",
            "4.2",
            "--evaluation-result",
            "pass",
            "--critique",
            "Sample evaluator critique",
            "--minimum-fix",
            "Sample evaluator fix",
            "--escalation-status",
            "watch",
            "--escalation-reason",
            "Sample escalation reason",
            "--recommended-action",
            "Sample escalation action",
            "--json",
            "--no-state",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    check(review_capture.returncode == 0, "capture-review.py runs successfully", failures)
    if review_capture.returncode == 0:
        captured = json.loads(review_capture.stdout)
        check(isinstance(captured.get("research_gate"), dict), "capture-review.py emits research_gate payload", failures)
        check(captured.get("research_gate", {}).get("status") == "captured", "capture-review.py records research status", failures)
        check(captured.get("research_gate", {}).get("summary") == "Sample research summary", "capture-review.py records research summary", failures)
        councils = captured.get("councils", {})
        check(isinstance(councils, dict), "capture-review.py emits council payloads", failures)
        check(councils.get("product_council", {}).get("summary") == "Sample product summary", "capture-review.py records product council summary", failures)
        check("Sample product dissent" in councils.get("product_council", {}).get("dissent", []), "capture-review.py records product council dissent", failures)
        secretariat = captured.get("secretariat", {})
        check(isinstance(secretariat, dict), "capture-review.py emits secretariat payloads", failures)
        check(
            secretariat.get("delivery_secretary", {}).get("summary") == "Sample delivery secretary summary",
            "capture-review.py records delivery secretary summary",
            failures,
        )
        check(
            secretariat.get("audit_secretary", {}).get("decision_record") == "Sample audit decision record",
            "capture-review.py records audit secretary decision record",
            failures,
        )
        scope_decision = captured.get("scope_decision", {})
        check(isinstance(scope_decision, dict), "capture-review.py emits scope_decision payload", failures)
        check(scope_decision.get("selected_goal") == "Sample selected goal", "capture-review.py records selected_goal", failures)
        check("Sample scope dissent" in scope_decision.get("dissent", []), "capture-review.py records scope dissent", failures)
        evaluation = captured.get("evaluation", {})
        check(isinstance(evaluation, dict), "capture-review.py emits evaluation payload", failures)
        check(evaluation.get("rubric_version") == "iteration-readiness-v1", "capture-review.py records rubric version", failures)
        check(evaluation.get("scores", {}).get("goal_clarity") == 4.5, "capture-review.py records evaluator scores", failures)
        check(evaluation.get("result") == "pass", "capture-review.py records evaluator result", failures)
        escalation = captured.get("escalation", {})
        check(isinstance(escalation, dict), "capture-review.py emits escalation payload", failures)
        check(escalation.get("status") == "watch", "capture-review.py records escalation status", failures)
        check(escalation.get("reason") == "Sample escalation reason", "capture-review.py records escalation reason", failures)

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
        check(
            "render-committee.py" in installer.stdout and "assert-implementation-readiness.py" in installer.stdout,
            "Project installer prints committee and readiness bootstrap guidance",
            failures,
        )
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
    validate_evaluator_gate(failures)
    validate_goal_selection_readiness(failures)
    validate_evaluator_brief(failures)
    validate_escalation_policy(failures)
    validate_review_reset_on_goal_change(failures)
    validate_session_continuation(failures)
    validate_structured_committee_flow(failures)
    helper = subprocess.run(
        [
            "python3",
            ".agent-loop/scripts/score-evaluator-readiness.py",
            "--score",
            "goal_clarity=4.0",
            "--score",
            "scope_fitness=4.0",
            "--score",
            "repo_safety=4.0",
            "--score",
            "validation_readiness=4.0",
            "--score",
            "state_durability=4.0",
            "--score",
            "publish_safety=4.0",
            "--json",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    check(helper.returncode == 0, "score-evaluator-readiness.py runs successfully", failures)
    if helper.returncode == 0:
        helper_payload = json.loads(helper.stdout)
        check(helper_payload.get("weighted_score") == 4.0, "score-evaluator-readiness.py computes the weighted score from the rubric", failures)
        check(helper_payload.get("result") == "pass", "score-evaluator-readiness.py computes the evaluator result from thresholds", failures)

    if failures:
        print(f"\nValidation failed with {len(failures)} issue(s).", file=sys.stderr)
        return 1

    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
