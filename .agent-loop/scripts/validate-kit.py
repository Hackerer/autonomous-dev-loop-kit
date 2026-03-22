#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
from shutil import copy2, rmtree
from pathlib import Path

from common import load_state, project_workspace_root, validate_committee


ROOT = Path(__file__).resolve().parents[2]


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"[通过] {message}")
    else:
        print(f"[失败] {message}")
        failures.append(message)


def is_positive_int(value: object) -> bool:
    return isinstance(value, int) and value > 0


def validate_json(path: Path, failures: list[str]) -> None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        print(f"[通过] JSON 解析：{path.relative_to(ROOT)}")
    except Exception as exc:  # pragma: no cover - defensive validation path
        print(f"[失败] JSON 解析：{path.relative_to(ROOT)} -> {exc}")
        failures.append(f"{path.relative_to(ROOT)} 的 JSON 解析失败")


def validate_python(path: Path, failures: list[str]) -> None:
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"[通过] Python 编译：{path.relative_to(ROOT)}")
    except py_compile.PyCompileError as exc:
        print(f"[失败] Python 编译：{path.relative_to(ROOT)} -> {exc.msg}")
        failures.append(f"{path.relative_to(ROOT)} 的 Python 编译失败")


def validate_skill(skill_md: Path, failures: list[str]) -> None:
    content = skill_md.read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    check(frontmatter is not None, f"存在 Frontmatter：{skill_md.relative_to(ROOT)}", failures)
    if frontmatter is None:
        return

    body = frontmatter.group(1)
    check(re.search(r"^name:\s+[a-z0-9-]+$", body, re.MULTILINE) is not None, f"存在技能名称：{skill_md.relative_to(ROOT)}", failures)
    check(re.search(r"^description:\s+.+$", body, re.MULTILINE) is not None, f"存在技能描述：{skill_md.relative_to(ROOT)}", failures)


def install_target_project(target: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AUTONOMOUS_DEV_LOOP_SKIP_REGISTRY"] = "1"
    result = subprocess.run(
        ["bash", "scripts/install-into-project.sh", "--target", str(target)],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    workspace = install_workspace_root(target)
    (workspace / ".agent-loop").mkdir(parents=True, exist_ok=True)
    (workspace / ".agent-loop" / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "docs" / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "docs" / "releases").mkdir(parents=True, exist_ok=True)
    copy2(ROOT / ".agent-loop" / "config.json", workspace / ".agent-loop" / "config.json")
    copy2(ROOT / ".agent-loop" / "state.json", workspace / ".agent-loop" / "state.json")
    copy2(ROOT / ".agent-loop" / "backlog.json", workspace / ".agent-loop" / "backlog.json")
    target.mkdir(parents=True, exist_ok=True)
    target_agent_loop = target / ".agent-loop"
    if target_agent_loop.exists() or target_agent_loop.is_symlink():
        if target_agent_loop.is_dir() and not target_agent_loop.is_symlink():
            rmtree(target_agent_loop)
        else:
            target_agent_loop.unlink()
    target_docs = target / "docs"
    if target_docs.exists() or target_docs.is_symlink():
        if target_docs.is_dir() and not target_docs.is_symlink():
            rmtree(target_docs)
        else:
            target_docs.unlink()
    target_agent_loop.symlink_to(workspace / ".agent-loop", target_is_directory=True)
    target_docs.symlink_to(workspace / "docs", target_is_directory=True)
    os.environ["AUTONOMOUS_DEV_LOOP_TARGET"] = str(target.resolve())
    os.environ["AUTONOMOUS_DEV_LOOP_WORKSPACE"] = str(workspace)
    return result


def install_workspace_root(target: Path) -> Path:
    snippet = """
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(root / ".agent-loop" / "scripts"))
from common import project_key

print(root / "docs" / "projects" / project_key(target))
"""
    result = subprocess.run(
        ["python3", "-", str(ROOT), str(target)],
        input=snippet,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to resolve install workspace root")
    return Path(result.stdout.strip()).resolve()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


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
        "release": {
            "number": 1,
            "title": "R1 seeded validation release",
            "summary": "Seeded release for validator coverage",
            "status": "planned",
            "brief": {
                "objective": "Seed validator coverage for report and publish gates.",
                "target_user_value": "Validator targets should exercise active release behavior.",
                "why_now": "Release planning is required by default.",
                "packaging_rationale": "A minimal seeded release keeps gate coverage aligned with the real protocol.",
                "scope_in": ["Gate review-state reporting and publication"],
                "scope_out": [],
                "release_acceptance": ["Validator target can write reports and publish iterations inside a release."],
                "launch_story": "Seed validator coverage for release-aware report and publish flows.",
                "deferred_items": [],
            },
            "goal_ids": [goal_id],
            "goal_titles": ["Gate review-state reporting and publication"],
            "completed_goal_ids": [],
            "task_iterations": [],
            "selected_at": "2026-03-15T00:00:00Z",
            "published_at": None,
            "report_path": None,
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
            "评审" in report_attempt.stderr or "活动目标" in report_attempt.stderr or "发布" in report_attempt.stderr,
            "write-report.py 说明如何满足评审状态门禁",
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-iteration.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(publish_attempt.returncode != 0, "publish-iteration.py rejects missing review state when committee review is required", failures)
        check(
            "评审" in publish_attempt.stderr or "活动目标" in publish_attempt.stderr or "发布" in publish_attempt.stderr,
            "publish-iteration.py 说明如何满足评审状态门禁",
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "assert-implementation-readiness.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(readiness_attempt.returncode != 0, "assert-implementation-readiness.py rejects missing evaluator pass", failures)
        check(
            "评审" in readiness_attempt.stderr or "实施" in readiness_attempt.stderr or "门禁" in readiness_attempt.stderr,
            "assert-implementation-readiness.py 说明评审门禁",
            failures,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a passing evaluator target", failures)

        write_json(target / ".agent-loop/state.json", seeded_state(goal_id, evaluator_result="pass"))
        readiness_attempt = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "assert-implementation-readiness.py")],
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "assert-implementation-readiness.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(readiness_attempt.returncode == 0, "assert-implementation-readiness.py allows advisory evaluator mode", failures)
        check(
            "建议模式" in readiness_attempt.stdout or "警告" in readiness_attempt.stdout or "不阻断" in readiness_attempt.stdout,
            "assert-implementation-readiness.py 清晰提示建议模式",
            failures,
        )

        report_attempt = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/write-report.py",
                "--analysis",
                "Advisory mode test",
                "--acceptance",
                "Advisory mode test",
                "--delivered",
                "Advisory mode test",
                "--reflection",
                "Advisory mode test",
                "--next-goal",
                "Advisory mode test",
            ],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(report_attempt.returncode != 0, "write-report.py still blocks advisory evaluator results without pass", failures)
        check(
            "评审" in report_attempt.stderr or "门禁" in report_attempt.stderr or "实施" in report_attempt.stderr,
            "write-report.py 说明报告仍需评审通过",
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "assert-implementation-readiness.py")],
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
                "--observation",
                "Seeded structured flow observation",
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
        check(report.returncode == 0, "结构化流程目标写出报告", failures)
        report_content = (target / "docs/reports/v1.md").read_text(encoding="utf-8")
        check("停止条件" in report_content, "结构化流程报告呈现停止条件", failures)
        check("选择原因" in report_content or "晋级决策" in report_content, "结构化流程报告呈现决策原因", failures)
        check("交付秘书" in report_content, "结构化流程报告呈现交付秘书输出", failures)
        check("审计秘书" in report_content, "结构化流程报告呈现审计秘书输出", failures)
        check("实验" in report_content, "结构化流程报告呈现实验部分", failures)
        check("实施门禁" in report_content, "结构化流程报告呈现实施门禁结果", failures)

        publish = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-iteration.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(publish.returncode == 0, "Structured-flow target publishes with commit-only", failures)


def validate_experiment_promotion_gate(failures: list[str]) -> None:
    goal_id = "experiment-promotion-gate"
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed an experiment-promotion target", failures)

        git_init = subprocess.run(["git", "init"], cwd=str(target), text=True, capture_output=True, check=False)
        check(git_init.returncode == 0, "Experiment-promotion target initializes git", failures)
        subprocess.run(["git", "config", "user.name", "Kit Validator"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "validator@example.com"], cwd=str(target), text=True, capture_output=True, check=False)

        config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        config["git"]["strategy"] = "commit-only"
        config["experiment"]["enabled"] = True
        write_json(target / ".agent-loop/config.json", config)

        state = seeded_state(goal_id, evaluator_result="pass")
        state["current_goal"]["title"] = "Experiment promotion gate"
        state["review_state"]["goal_title"] = "Experiment promotion gate"
        state["review_state"]["experiment"] = {
            "status": "captured",
            "base": {
                "label": "Baseline release",
                "metric_name": "review_state.evaluation.weighted_score",
                "metric_value": 4.8,
            },
            "candidate": {
                "label": "Candidate release",
                "metric_name": "review_state.evaluation.weighted_score",
                "metric_value": 4.0,
            },
            "comparison": {
                "status": "captured",
                "direction": "higher",
                "delta": -0.8,
                "result": "revise",
                "rationale": "Candidate is below the durable base score.",
            },
            "promotion": {
                "status": "captured",
                "decision": "revise",
                "reason": "Candidate has not beaten the base yet.",
                "next_action": "Continue iterating before promotion.",
            },
        }
        state["history"] = [
            {
                "session_id": "session-20260315-000000",
                "iteration": 0,
                "goal": "Baseline release",
                "goal_id": "baseline-release",
                "evaluation_result": "pass",
                "validation_status": "passed",
                "candidate_metric_value": 4.8,
                "experiment_decision": "promote",
            }
        ]
        state["draft_goal"] = state["current_goal"]
        state["draft_iteration"] = 1
        state["draft_report"] = "docs/reports/v1.md"
        state["release"] = {
            "number": 1,
            "title": "R1 seeded experiment release",
            "summary": "Seeded release for experiment gate validation",
            "status": "planned",
            "brief": {
                "objective": "Validate experiment promotion gating.",
                "target_user_value": "Candidate versions should only promote when they beat base.",
                "why_now": "This release exercises the candidate-versus-base contract.",
                "packaging_rationale": "The release packages one experiment gate change.",
                "scope_in": ["Experiment promotion gate"],
                "scope_out": [],
                "release_acceptance": ["Candidate promotion requires a better metric than base."],
                "launch_story": "Prove the candidate can beat base before promotion.",
                "deferred_items": [],
                "baseline_release": {
                    "number": 0,
                    "title": "Baseline release",
                    "metric_name": "review_state.evaluation.weighted_score",
                    "metric_value": 4.8,
                },
                "promotion_rule": "Candidate metric must beat the current base metric before publish.",
            },
            "goal_ids": [goal_id],
            "goal_titles": ["Experiment promotion gate"],
            "completed_goal_ids": [],
            "task_iterations": [],
            "selected_at": "2026-03-15T00:00:00Z",
            "published_at": None,
            "report_path": None,
        }
        write_json(target / ".agent-loop/state.json", state)
        (target / "docs/reports").mkdir(parents=True, exist_ok=True)
        (target / "docs/reports/v1.md").write_text("# Task Iteration v1 Report\n", encoding="utf-8")

        blocked = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-iteration.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(blocked.returncode != 0, "publish-iteration.py 阻止未超过基线的候选版本", failures)
        check(
            "基线" in blocked.stderr or "候选" in blocked.stderr,
            "publish-iteration.py 解释候选版本为何被基线比较阻止",
            failures,
        )

        state = load_state(target)
        state["review_state"]["experiment"]["candidate"]["metric_value"] = 5.3
        state["review_state"]["experiment"]["comparison"]["delta"] = 0.5
        state["review_state"]["experiment"]["comparison"]["result"] = "promote"
        state["review_state"]["experiment"]["promotion"]["decision"] = "promote"
        state["review_state"]["experiment"]["promotion"]["reason"] = "Candidate beats the base."
        write_json(target / ".agent-loop/state.json", state)

        promoted = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-iteration.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(promoted.returncode == 0, "publish-iteration.py 晋级超过基线的候选版本", failures)


def validate_release_flow(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a bundled-release target", failures)

        git_init = subprocess.run(["git", "init"], cwd=str(target), text=True, capture_output=True, check=False)
        check(git_init.returncode == 0, "Bundled-release target initializes git", failures)
        subprocess.run(["git", "config", "user.name", "Kit Validator"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "validator@example.com"], cwd=str(target), text=True, capture_output=True, check=False)

        config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        config["git"]["strategy"] = "commit-only"
        write_json(target / ".agent-loop/config.json", config)

        backlog = [
            {"id": "goal-a", "title": "Goal A", "priority": "critical", "status": "pending", "acceptance": []},
            {"id": "goal-b", "title": "Goal B", "priority": "high", "status": "pending", "acceptance": []},
        ]
        write_json(target / ".agent-loop/backlog.json", backlog)

        started = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "set-loop-session.py"), "--iterations", "1"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(started.returncode == 0, "Bundled-release target starts a release session", failures)

        planned = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/plan-release.py",
                "--goal-id",
                "goal-a",
                "--goal-id",
                "goal-b",
                "--scope-out",
                "Goal C stays out of this validator release",
                "--deferred-item",
                "Goal C stays deferred",
                "--release-acceptance",
                "Validator bundled release acceptance",
            ],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(planned.returncode == 0, "plan-release.py bundles multiple goals into one release", failures)
        updated_state = load_state(target)
        brief = updated_state.get("release", {}).get("brief", {})
        check(bool(brief.get("objective")), "plan-release.py records a release objective", failures)
        check(bool(brief.get("target_user_value")), "plan-release.py records target user value", failures)
        check(isinstance(brief.get("release_acceptance"), list), "plan-release.py records release acceptance", failures)

        state = load_state(target)
        state["release"]["status"] = "ready_to_release"
        state["release"]["completed_goal_ids"] = ["goal-a", "goal-b"]
        state["release"]["task_iterations"] = [
            {"iteration": 1, "goal": "Goal A", "goal_id": "goal-a", "report": "docs/reports/v1.md", "published_at": "2026-03-15T00:00:00Z"},
            {"iteration": 2, "goal": "Goal B", "goal_id": "goal-b", "report": "docs/reports/v2.md", "published_at": "2026-03-15T00:05:00Z"},
        ]
        state["last_validation"] = {
            "status": "passed",
            "ran_at": "2026-03-15T00:06:00Z",
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
        }
        write_json(target / ".agent-loop/state.json", state)
        (target / "docs/reports").mkdir(parents=True, exist_ok=True)
        (target / "docs/reports/v1.md").write_text(
            "# Task Iteration v1 Report\n\n## Delivered\n- Delivered A\n\n## Full Validation\n- `python3 .agent-loop/scripts/validate-kit.py` -> PASS (exit 0)\n\n## Key Observations\n- Observation A\n",
            encoding="utf-8",
        )
        (target / "docs/reports/v2.md").write_text(
            "# Task Iteration v2 Report\n\n## Delivered\n- Delivered B\n\n## Full Validation\n- `python3 .agent-loop/scripts/validate-kit.py` -> PASS (exit 0)\n\n## Key Observations\n- Observation B\n",
            encoding="utf-8",
        )

        release_report = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/write-release-report.py",
                "--summary",
                "Ship bundled release R1",
                "--output-note",
                "Bundled release validator output note",
                "--next-release",
                "Stop after validator release",
            ],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(release_report.returncode == 0, "write-release-report.py aggregates the bundled release", failures)
        release_report_content = (target / "docs/releases/R1.md").read_text(encoding="utf-8")
        check("产品发布简报" in release_report_content, "发布报告包含产品发布简报", failures)
        check("实验基线" in release_report_content, "发布报告包含实验基线", failures)
        check("Delivered A" in release_report_content and "Delivered B" in release_report_content, "发布报告汇总已交付范围", failures)
        check("技术验证" in release_report_content, "发布报告包含技术验证状态", failures)

        published = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-release.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(published.returncode == 0, "publish-release.py publishes the bundled release with commit-only", failures)
        updated_state = load_state(target)
        check(updated_state.get("session", {}).get("completed_releases") == 1, "Bundled release publish increments completed releases", failures)
        check(len(updated_state.get("release_history", [])) >= 1, "Bundled release publish records release history", failures)
        clean_after_release = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(clean_after_release.returncode == 0 and clean_after_release.stdout.strip() == "", "Bundled release publish leaves a clean worktree", failures)

        backlog.append({"id": "goal-c", "title": "Goal C", "priority": "high", "status": "pending", "acceptance": []})
        write_json(target / ".agent-loop/backlog.json", backlog)
        updated_state["session"]["completed_releases"] = 0
        write_json(target / ".agent-loop/state.json", updated_state)
        replanned = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "plan-release.py"), "--goal-id", "goal-c"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(replanned.returncode == 0, "plan-release.py can continue with consecutive release numbers from release history", failures)
        if replanned.returncode == 0:
            next_state = load_state(target)
            check(next_state.get("release", {}).get("number") == 2, "plan-release.py keeps release numbers consecutive", failures)

        orphan_state = load_state(target)
        orphan_state["current_goal"] = {"id": "", "title": "", "selected_at": "2026-03-15T00:10:00Z", "source": ".agent-loop/backlog.json"}
        orphan_state["draft_goal"] = orphan_state["current_goal"]
        orphan_state["draft_iteration"] = 3
        orphan_state["draft_report"] = "docs/reports/v3.md"
        write_json(target / ".agent-loop/state.json", orphan_state)
        (target / "docs/reports/v3.md").write_text("# Task Iteration v3 Report\n", encoding="utf-8")
        orphan_publish = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-iteration.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(orphan_publish.returncode != 0, "publish-iteration.py rejects orphan iteration publish attempts", failures)

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a failed-publish rollback target", failures)

        git_init = subprocess.run(["git", "init"], cwd=str(target), text=True, capture_output=True, check=False)
        check(git_init.returncode == 0, "Failed-publish target initializes git", failures)
        subprocess.run(["git", "config", "user.name", "Kit Validator"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "validator@example.com"], cwd=str(target), text=True, capture_output=True, check=False)

        config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        config["git"]["strategy"] = "direct-push"
        config["git"]["require_remote"] = True
        write_json(target / ".agent-loop/config.json", config)

        write_json(
            target / ".agent-loop/backlog.json",
            [{"id": "goal-a", "title": "Goal A", "priority": "high", "status": "pending", "acceptance": []}],
        )
        failed_publish_state = seeded_state("goal-a", evaluator_result="pass")
        failed_publish_state["current_goal"]["title"] = "Goal A"
        failed_publish_state["review_state"]["goal_title"] = "Goal A"
        failed_publish_state["draft_goal"] = failed_publish_state["current_goal"]
        failed_publish_state["draft_iteration"] = 1
        failed_publish_state["draft_report"] = "docs/reports/v1.md"
        write_json(target / ".agent-loop/state.json", failed_publish_state)
        (target / "docs/reports").mkdir(parents=True, exist_ok=True)
        (target / "docs/reports/v1.md").write_text("# Task Iteration v1 Report\n", encoding="utf-8")

        failed_publish = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-iteration.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(failed_publish.returncode != 0, "publish-iteration.py fails before mutating state when publish target is invalid", failures)
        after_failed_publish_state = load_state(target)
        after_failed_publish_backlog = json.loads((target / ".agent-loop/backlog.json").read_text(encoding="utf-8"))
        check(
            after_failed_publish_state.get("session", {}).get("completed_iterations") == 0,
            "Failed publish does not advance completed task iterations",
            failures,
        )
        check(
            isinstance(after_failed_publish_state.get("current_goal"), dict)
            and after_failed_publish_state.get("current_goal", {}).get("id") == "goal-a",
            "Failed publish preserves the active goal selection",
            failures,
        )
        check(
            after_failed_publish_backlog[0].get("status") == "pending",
            "Failed publish does not mark the backlog goal as completed",
            failures,
        )


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
            "target_releases": 1,
            "completed_releases": 0,
            "target_iterations": 1,
            "completed_iterations": 0,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": None,
        }
        state["release"] = {
            "number": 1,
            "title": "R1 seeded quality blocker release",
            "summary": "Seeded release for quality blocker validation",
            "status": "planned",
            "goal_ids": ["seeded-goal"],
            "goal_titles": ["Seeded goal"],
            "completed_goal_ids": [],
            "task_iterations": [],
            "selected_at": "2026-03-15T00:00:00Z",
            "published_at": None,
            "report_path": None,
        }
        state["project_data"]["quality_path"] = ".agent-loop/data/data-quality.json"
        state["project_data"]["last_quality_score"] = 45
        state["project_data"]["last_quality_status"] = "insufficient"
        write_json(target / ".agent-loop/state.json", state)

        blocked = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "select-next-goal.py")],
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
            "target_releases": 1,
            "completed_releases": 0,
            "target_iterations": 1,
            "completed_iterations": 0,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": None,
        }
        state["release"] = {
            "number": 1,
            "title": "R1 seeded research blocker release",
            "summary": "Seeded release for research blocker validation",
            "status": "planned",
            "goal_ids": ["seeded-goal"],
            "goal_titles": ["Seeded goal"],
            "completed_goal_ids": [],
            "task_iterations": [],
            "selected_at": "2026-03-15T00:00:00Z",
            "published_at": None,
            "report_path": None,
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "select-next-goal.py")],
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "render-evaluator-brief.py"), "--json"],
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "assess-escalation.py"), "--json"],
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
                "session_id": "session-20260315-000000",
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "assess-escalation.py"), "--apply", "--json"],
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "capture-review.py"), "--research", "First goal finding"],
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
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "capture-review.py"), "--research", "Second goal finding"],
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
            "target_releases": 2,
            "completed_releases": 2,
            "target_iterations": 2,
            "completed_iterations": 2,
            "started_at": "2026-03-15T00:00:00Z",
            "ended_at": "2026-03-15T00:10:00Z",
        }
        state["status"] = "session_completed"
        write_json(target / ".agent-loop/state.json", state)

        continued = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "continue-loop-session.py"), "--add", "3"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(continued.returncode == 0, "continue-loop-session.py extends a completed session", failures)
        if continued.returncode == 0:
            updated_state = load_state(target)
            check(updated_state.get("session", {}).get("target_releases") == 5, "continue-loop-session.py preserves completed progress while extending target", failures)
            check(updated_state.get("session", {}).get("status") == "active", "continue-loop-session.py reopens the session as active", failures)


def validate_session_reset_and_structured_review_content(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a session-reset target", failures)

        state = load_state(target)
        state["current_goal"] = {"id": "legacy-goal", "title": "Legacy Goal", "selected_at": "2026-03-15T00:00:00Z", "source": ".agent-loop/backlog.json"}
        state["review_state"] = {
            "status": "captured",
            "goal_id": "legacy-goal",
            "goal_title": "Legacy Goal",
            "research_findings": ["Legacy research"],
            "committee_feedback": ["Legacy feedback"],
            "committee_decision": ["Legacy decision"],
            "reflection_notes": [],
            "evaluation": {"status": "captured", "result": "fail", "rubric_version": "iteration-readiness-v1", "scores": {}, "weighted_score": 1.0, "critique": [], "minimum_fixes_required": []},
        }
        state["consecutive_failures"] = 2
        write_json(target / ".agent-loop/state.json", state)

        started = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "set-loop-session.py"), "--iterations", "2"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(started.returncode == 0, "set-loop-session.py starts a fresh remediation session", failures)
        if started.returncode == 0:
            updated_state = load_state(target)
            check(updated_state.get("review_state", {}).get("status") == "not_started", "set-loop-session.py resets review_state for a fresh session", failures)
            check(updated_state.get("consecutive_failures") == 0, "set-loop-session.py resets consecutive failure count", failures)
            check(updated_state.get("current_goal") is None, "set-loop-session.py clears the active goal", failures)
            check(updated_state.get("release", {}).get("status") == "not_planned", "set-loop-session.py resets the active release shape", failures)

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a structured-review-content target", failures)

        structured_state = seeded_state("structured-review", evaluator_result="pass")
        structured_state["review_state"]["research_findings"] = []
        structured_state["review_state"]["committee_feedback"] = []
        structured_state["review_state"]["committee_decision"] = []
        structured_state["review_state"]["research_gate"] = {
            "status": "captured",
            "summary": "Structured review summary",
            "evidence_refs": [],
            "data_quality_score": 100,
            "open_gaps": [],
        }
        structured_state["review_state"]["scope_decision"] = {
            "status": "captured",
            "selected_goal": "structured-review",
            "why_selected": "Structured review content should satisfy the gate.",
            "scope_in": ["Structured scope in"],
            "scope_out": [],
            "assumptions": [],
            "risks": [],
            "required_validation": [],
            "stop_conditions": [],
            "dissent": [],
            "next_action": "",
        }
        write_json(target / ".agent-loop/state.json", structured_state)

        readiness_attempt = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "assert-implementation-readiness.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(readiness_attempt.returncode == 0, "Structured review-state content satisfies the readiness gate without legacy flat fields", failures)


def validate_usage_logging(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        install_workspace = install_workspace_root(target)
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed a usage-logging target", failures)

        install_log = install_workspace / ".agent-loop/data/usage-log.jsonl"
        session_log = target / ".agent-loop/data/usage-log.jsonl"
        check(install_log.exists(), "项目安装器在 kit 工作区项目目录中记录安装使用事件", failures)

        started = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "set-loop-session.py"), "--iterations", "2"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(started.returncode == 0, "set-loop-session.py records a session start on a usage-logging target", failures)
        usage_rows = read_jsonl(session_log)
        session_started_row = next((row for row in usage_rows if row.get("event") == "session_started"), {})
        session_context = session_started_row.get("session", {}) if isinstance(session_started_row, dict) else {}
        check(bool(session_context.get("id")), "Usage-log events capture a stable session id", failures)

        extended = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "continue-loop-session.py"), "--add", "1"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(extended.returncode == 0, "continue-loop-session.py records a session extension on a usage-logging target", failures)

        config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        config["git"]["strategy"] = "commit-only"
        write_json(target / ".agent-loop/config.json", config)

        git_init = subprocess.run(["git", "init"], cwd=str(target), text=True, capture_output=True, check=False)
        check(git_init.returncode == 0, "Usage-logging target initializes git", failures)
        subprocess.run(["git", "config", "user.name", "Kit Validator"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "validator@example.com"], cwd=str(target), text=True, capture_output=True, check=False)

        existing_state = json.loads((target / ".agent-loop/state.json").read_text(encoding="utf-8"))
        state = seeded_state("usage-log-publish", evaluator_result="pass")
        state["session"] = existing_state.get("session", state.get("session", {}))
        state["draft_iteration"] = 1
        state["draft_report"] = "docs/reports/v1.md"
        state["draft_goal"] = state["current_goal"]
        write_json(target / ".agent-loop/state.json", state)
        (target / "docs/reports").mkdir(parents=True, exist_ok=True)
        (target / "docs/reports/v1.md").write_text("# Usage Log Test Report\n", encoding="utf-8")

        publish = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "publish-iteration.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(publish.returncode == 0, "publish-iteration.py records a publish usage event", failures)
        clean_after_iteration = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(
            clean_after_iteration.returncode == 0 and clean_after_iteration.stdout.strip() == "",
            "publish-iteration.py leaves a clean worktree after a successful commit-only publish",
            failures,
        )

        config["validation"]["commands"] = [
            {
                "name": "forced-failure",
                "command": "python3 -c 'import sys; sys.exit(1)'",
                "required": True,
            }
        ]
        write_json(target / ".agent-loop/config.json", config)
        failed_validation = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "run-full-validation.py")],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(failed_validation.returncode != 0, "run-full-validation.py can emit a failing validation event", failures)

        analyzer = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/analyze-usage-logs.py",
                "--json",
                "--log",
                str(install_log),
                "--log",
                str(session_log),
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        check(analyzer.returncode == 0, "analyze-usage-logs.py runs successfully", failures)
        if analyzer.returncode == 0:
            payload = json.loads(analyzer.stdout)
            events = payload.get("events_by_type", {})
            check(events.get("kit_installed", 0) >= 1, "Usage-log analysis includes install events", failures)
            check(events.get("session_started", 0) >= 1, "Usage-log analysis includes session start events", failures)
            check(events.get("session_extended", 0) >= 1, "Usage-log analysis includes session extension events", failures)
        check(events.get("iteration_published", 0) >= 1, "使用日志分析包含发布事件", failures)
            check(events.get("validation_failed", 0) >= 1, "Usage-log analysis includes failing validation events", failures)
            check(int(payload.get("session_count", 0)) >= 1, "Usage-log analysis summarizes session-level usage", failures)
            sessions = payload.get("sessions", [])
            check(isinstance(sessions, list) and bool(sessions), "Usage-log analysis exposes session summaries", failures)

        session_log.write_text(session_log.read_text(encoding="utf-8") + "{not-json}\n", encoding="utf-8")
        analyzer_with_invalid_row = subprocess.run(
            [
                "python3",
                ".agent-loop/scripts/analyze-usage-logs.py",
                "--json",
                "--log",
                str(install_log),
                "--log",
                str(session_log),
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        check(analyzer_with_invalid_row.returncode == 0, "analyze-usage-logs.py tolerates malformed usage-log rows", failures)
        if analyzer_with_invalid_row.returncode == 0:
            payload = json.loads(analyzer_with_invalid_row.stdout)
            check(int(payload.get("invalid_row_count", 0)) >= 1, "Usage-log analysis reports skipped malformed rows", failures)


def validate_operator_recovery_tools(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "target-repo"
        installer = install_target_project(target)
        check(installer.returncode == 0, "Project installer can seed an operator-recovery target", failures)

        status_run = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "loop-status.py"), "--json"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(status_run.returncode == 0, "loop-status.py runs successfully", failures)
        if status_run.returncode == 0:
            payload = json.loads(status_run.stdout)
            check(isinstance(payload.get("session"), dict), "loop-status.py exposes session details", failures)
            check(isinstance(payload.get("release"), dict), "loop-status.py exposes release details", failures)

        doctor_run = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "loop-doctor.py"), "--json"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(doctor_run.returncode == 0, "loop-doctor.py runs successfully", failures)
        if doctor_run.returncode == 0:
            payload = json.loads(doctor_run.stdout)
            findings = payload.get("findings", [])
            check(isinstance(findings, list), "loop-doctor.py exposes structured findings", failures)
            check(bool(findings), "loop-doctor.py detects missing session or release setup", failures)

        config = json.loads((target / ".agent-loop/config.json").read_text(encoding="utf-8"))
        config["git"]["strategy"] = "direct-push"
        config["git"]["remote"] = "origin"
        write_json(target / ".agent-loop/config.json", config)
        subprocess.run(["git", "init"], cwd=str(target), text=True, capture_output=True, check=False)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.com/not-github.git"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        doctor_remote = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "loop-doctor.py"), "--json"],
            cwd=str(target),
            text=True,
            capture_output=True,
            check=False,
        )
        check(doctor_remote.returncode == 0, "loop-doctor.py can inspect publish-target remote issues", failures)
        if doctor_remote.returncode == 0:
            payload = json.loads(doctor_remote.stdout)
            findings = payload.get("findings", [])
            issues = " ".join(item.get("issue", "") for item in findings if isinstance(item, dict))
            check("github" in issues.lower(), "loop-doctor.py reports non-GitHub publish blockers", failures)


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
        ROOT / ".agent-loop/scripts/plan-release.py",
        ROOT / ".agent-loop/scripts/analyze-usage-logs.py",
        ROOT / ".agent-loop/scripts/loop-status.py",
        ROOT / ".agent-loop/scripts/loop-doctor.py",
        ROOT / ".agent-loop/scripts/record-usage-event.py",
        ROOT / ".agent-loop/scripts/publish-release.py",
        ROOT / ".agent-loop/scripts/render-evaluator-brief.py",
        ROOT / ".agent-loop/scripts/score-evaluator-readiness.py",
        ROOT / ".agent-loop/scripts/write-release-report.py",
        ROOT / ".agents/skills/autonomous-dev-loop/SKILL.md",
        ROOT / ".agents/skills/autonomous-dev-loop/agents/openai.yaml",
        ROOT / ".claude/skills/autonomous-dev-loop/SKILL.md",
        ROOT / ".claude/skills/autonomous-dev-loop/agents/openai.yaml",
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

    for skill_yaml, label in [
        (ROOT / ".agents/skills/autonomous-dev-loop/agents/openai.yaml", "Codex"),
        (ROOT / ".claude/skills/autonomous-dev-loop/agents/openai.yaml", "Claude"),
    ]:
        if skill_yaml.exists():
            yaml_text = skill_yaml.read_text(encoding="utf-8")
            check("display_name:" in yaml_text, f"{label} skill metadata includes a display name", failures)
            check("default_prompt:" in yaml_text, f"{label} skill metadata includes a default prompt", failures)

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
    check(
        is_positive_int(config.get("planning", {}).get("max_releases_per_session")),
        "Planning max_releases_per_session is a positive integer",
        failures,
    )
    usage_logging = config.get("usage_logging", {})
    check(isinstance(usage_logging, dict), "Usage logging config is present", failures)
    check(usage_logging.get("enabled") is True, "Usage logging defaults to enabled", failures)
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
    experiment_config = config.get("experiment", {})
    check(isinstance(experiment_config, dict), "Experiment config is present", failures)
    check(experiment_config.get("enabled") is False, "Experiment layer defaults to disabled for opt-in use", failures)
    check(
        experiment_config.get("baseline_strategy") == "last_promoted_release",
        "Experiment layer uses the last promoted release as the baseline strategy",
        failures,
    )
    rubric = json.loads((ROOT / ".agent-loop/references/iteration-readiness-rubric.json").read_text(encoding="utf-8"))
    check(rubric.get("id") == "iteration-readiness-v1", "Evaluator rubric id is correct", failures)
    check(isinstance(rubric.get("criteria"), dict) and len(rubric.get("criteria", {})) >= 6, "Evaluator rubric exposes weighted criteria", failures)
    review_state = state.get("review_state", {})
    check(isinstance(review_state.get("research_gate"), dict), "State normalization exposes research_gate", failures)
    check(isinstance(review_state.get("councils"), dict), "State normalization exposes council summaries", failures)
    check(isinstance(review_state.get("secretariat"), dict), "State normalization exposes secretariat summaries", failures)
    check(isinstance(review_state.get("scope_decision"), dict), "State normalization exposes scope_decision", failures)
    check(isinstance(review_state.get("evaluation"), dict), "State normalization exposes evaluation", failures)
    check(isinstance(review_state.get("experiment"), dict), "State normalization exposes experiment", failures)
    check(isinstance(review_state.get("escalation"), dict), "State normalization exposes escalation", failures)

    generated_project_data = ROOT / ".agent-loop/data/project-data.generated.json"
    collector = subprocess.run(
        ["python3", str(ROOT / ".agent-loop" / "scripts" / "collect-project-data.py"), "--output", str(generated_project_data), "--no-state"],
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
        check(isinstance(latest_review_state.get("experiment"), dict), "Project data includes experiment summary", failures)
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
        ["python3", str(ROOT / ".agent-loop" / "scripts" / "render-committee.py"), "--json"],
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
        workspace = Path(tmp_dir) / "kit-workspace"
        env = os.environ.copy()
        env["AUTONOMOUS_DEV_LOOP_WORKSPACE"] = str(workspace)
        target.mkdir(parents=True, exist_ok=True)
        installer = subprocess.run(
            ["bash", "scripts/install-into-project.sh", "--target", str(target)],
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        check(installer.returncode == 0, "install-into-project.sh runs successfully", failures)
        check(
            "does not write kit assets" in installer.stdout.lower() or "no-copy" in installer.stdout.lower(),
            "Project installer clearly reports the non-invasive default",
            failures,
        )
        check(
            not any(target.iterdir()),
            "Project installer leaves the target project untouched by default",
            failures,
        )
        usage_log = workspace / ".agent-loop/data/usage-log.jsonl"
        events = [item for item in read_jsonl(usage_log) if item.get("event") == "kit_installed"]
        check(
            any(
                item.get("payload", {}).get("target_repo") == str(target.resolve())
                and item.get("payload", {}).get("mode") == "no-copy"
                for item in events
            ),
            "Project installer records a kit-local no-copy install event in the per-project workspace",
            failures,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "external-target"
        workspace = Path(tmp_dir) / "kit-workspace"
        env = os.environ.copy()
        env["AUTONOMOUS_DEV_LOOP_TARGET"] = str(target)
        env["AUTONOMOUS_DEV_LOOP_WORKSPACE"] = str(workspace)

        started = subprocess.run(
            ["python3", str(ROOT / ".agent-loop" / "scripts" / "set-loop-session.py"), "--iterations", "2"],
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        check(started.returncode == 0, "set-loop-session.py can operate on an external target from the kit workspace", failures)

        usage_log = workspace / ".agent-loop/data/usage-log.jsonl"
        check(usage_log.exists(), "External-target usage events are written into the kit workspace project folder", failures)
        usage_rows = read_jsonl(usage_log)
        session_started_row = next((row for row in usage_rows if row.get("event") == "session_started"), {})
        workspace_info = session_started_row.get("workspace", {}) if isinstance(session_started_row, dict) else {}
        repo_info = session_started_row.get("repo", {}) if isinstance(session_started_row, dict) else {}
        check(str(workspace.resolve()) == workspace_info.get("root"), "Usage-log events record the kit workspace root", failures)
        check(str(target.resolve()) == repo_info.get("root"), "Usage-log events record the external target root separately", failures)

    validate_review_gate(failures)
    validate_evaluator_gate(failures)
    validate_goal_selection_readiness(failures)
    validate_evaluator_brief(failures)
    validate_escalation_policy(failures)
    validate_review_reset_on_goal_change(failures)
    validate_session_continuation(failures)
    validate_session_reset_and_structured_review_content(failures)
    validate_usage_logging(failures)
    validate_operator_recovery_tools(failures)
    validate_structured_committee_flow(failures)
    validate_experiment_promotion_gate(failures)
    validate_release_flow(failures)
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
        print(f"\n验证失败，共 {len(failures)} 个问题。", file=sys.stderr)
        return 1

    print("\n验证通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
