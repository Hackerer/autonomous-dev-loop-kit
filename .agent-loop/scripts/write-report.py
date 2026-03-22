#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from common import (
    append_usage_log,
    cli_info,
    committee_summary,
    implementation_gate_status,
    LoopError,
    goal_title,
    load_config,
    load_json,
    load_state,
    require_goal_in_active_release,
    require_selected_goal,
    release_summary,
    relpath,
    reporting_path,
    require_evaluator_pass,
    require_green_validation,
    require_review_state,
    resolve_execution_roots,
    save_state,
    session_summary,
)


def bullet_lines(values: list[str], fallback: str) -> list[str]:
    if not values:
        return [f"- {fallback}"]
    return [f"- {value}" for value in values]


def merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*primary, *secondary]:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def prefixed_lines(prefix: str, values: list[str]) -> list[str]:
    return [f"{prefix}{value}" for value in values if value.strip()]


def translate_report_text(text: str) -> str:
    replacements = [
        ("## Session Progress", "## 会话进度"),
        ("## Current State Analysis", "## 当前状态分析"),
        ("## Research", "## 研究"),
        ("## Committee Review", "## 委员会评审"),
        ("## Secretariat", "## 秘书处"),
        ("## Task Goal", "## 任务目标"),
        ("## Scope Decision", "## 范围决策"),
        ("## Key Observations", "## 关键观察"),
        ("## Evidence Sources", "## 证据来源"),
        ("## Data Quality", "## 数据质量"),
        ("## Delivered", "## 已交付内容"),
        ("## Evaluation Readiness", "## 评审准备情况"),
        ("## Experiment", "## 实验"),
        ("## Stop And Escalation", "## 停止与升级"),
        ("## Full Validation", "## 全量验证"),
        ("## Reflection", "## 反思"),
        ("## Proposed Next Goal", "## 下一目标建议"),
        ("Release session progress:", "发布会话进度："),
        ("Task iteration progress:", "任务迭代进度："),
        ("Active release:", "当前发布："),
        ("# Task Iteration v", "# 任务迭代 v"),
        ("Task Iteration", "任务迭代"),
        (" Report", " 报告"),
        ("- Goal:", "- 目标："),
        ("Implementation gate:", "实施门禁："),
        ("Latest quality status:", "最新数据质量状态："),
        ("Blocking gaps:", "阻塞问题："),
        ("Research gate summary:", "研究门总结："),
        ("Open gap:", "未闭合问题："),
        ("Members:", "成员："),
        ("no named members", "未指定成员"),
        ("Product Council summary:", "产品委员会总结："),
        ("Product Council decision:", "产品委员会决策："),
        ("Product Council dissent:", "产品委员会异议："),
        ("Architecture Council summary:", "架构委员会总结："),
        ("Architecture Council decision:", "架构委员会决策："),
        ("Architecture Council dissent:", "架构委员会异议："),
        ("Operator Council summary:", "运营委员会总结："),
        ("Operator Council decision:", "运营委员会决策："),
        ("Operator Council dissent:", "运营委员会异议："),
        ("Delivery Secretary summary:", "交付秘书总结："),
        ("Delivery Secretary next action:", "交付秘书下一步："),
        ("Audit Secretary summary:", "审计秘书总结："),
        ("Audit decision record:", "审计决策记录："),
        ("Audit open gap:", "审计未闭合问题："),
        ("Audit dissent:", "审计异议："),
        ("Why selected:", "选择原因："),
        ("Scope in:", "范围内："),
        ("Scope out:", "范围外："),
        ("Assumption:", "假设："),
        ("Risk:", "风险："),
        ("Required validation:", "必需验证："),
        ("Stop condition:", "停止条件："),
        ("Scope dissent:", "范围异议："),
        ("Next action:", "下一步："),
        ("Implementation gate:", "实施门禁："),
        ("Evaluator outcome:", "评审结果："),
        ("Evaluator scores:", "评审分项："),
        ("Evaluator critique:", "评审批评："),
        ("Minimum fix required:", "最低修复要求："),
        ("Base:", "基线："),
        ("Candidate:", "候选："),
        ("Comparison:", "对比结果："),
        ("Comparison rationale:", "对比说明："),
        ("Promotion decision:", "晋级决策："),
        ("Promotion reason:", "晋级原因："),
        ("Promotion next action:", "晋级下一步："),
        ("Escalation status:", "升级状态："),
        ("Escalation reason:", "升级原因："),
        ("Escalation action:", "建议动作："),
        ("No experiment comparison was captured for this goal.", "当前目标未记录实验对比。"),
        ("Record open gaps, stop conditions, and escalation status so a later operator can see why the loop would stop or escalate.", "请记录未闭合问题、停止条件和升级状态，方便后续操作者理解为什么循环会停止或升级。"),
        ("No validation results were recorded.", "未记录验证结果。"),
        ("Reflect on requirement clarity and architectural impact.", "请反思需求清晰度与架构影响。"),
        ("Propose the next highest-value task inside the current release or the next release theme.", "请提出当前发布内或下一发布主题下的最高价值下一任务。"),
        ("Task iteration v", "任务迭代 v"),
    ]
    for src, dst in replacements:
        text = text.replace(src, dst)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a task-iteration report for the next autonomous loop step.")
    parser.add_argument("--analysis", action="append", default=[], help="Current-state analysis bullet.")
    parser.add_argument("--research", action="append", default=[], help="Research bullet gathered before goal selection.")
    parser.add_argument("--acceptance", action="append", default=[], help="Acceptance bullet for this version.")
    parser.add_argument("--committee-feedback", action="append", default=[], help="Committee feedback bullet.")
    parser.add_argument("--committee-decision", action="append", default=[], help="Committee decision bullet.")
    parser.add_argument("--observation", action="append", default=[], help="Key observation bullet from the ReAct cycle.")
    parser.add_argument("--source", action="append", default=[], help="Evidence source bullet for this version.")
    parser.add_argument("--quality-note", action="append", default=[], help="Data-quality bullet for this version.")
    parser.add_argument("--delivered", action="append", default=[], help="Delivered change bullet.")
    parser.add_argument("--reflection", action="append", default=[], help="Reflection bullet.")
    parser.add_argument("--next-goal", action="append", default=[], help="Next-goal proposal bullet.")
    args = parser.parse_args()

    kit_root, target_root, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    cli_info("正在生成任务迭代报告。")
    validation = require_green_validation(state)
    session = session_summary(state)
    release = release_summary(state)

    iteration = int(state.get("iteration", 0)) + 1
    report_path = reporting_path(workspace_root, config, iteration)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    goal = require_selected_goal(state)
    require_goal_in_active_release(config, state, goal)
    goal_label = goal_title(goal)
    today = datetime.now().date().isoformat()
    project_data = state.get("project_data", {})
    review_state = require_review_state(config, state, goal)
    require_evaluator_pass(config, state, goal)
    review_research = list(review_state.get("research_findings", []))
    review_feedback = list(review_state.get("committee_feedback", []))
    review_decision = list(review_state.get("committee_decision", []))
    review_reflection = list(review_state.get("reflection_notes", []))
    research_gate = review_state.get("research_gate", {})
    councils = review_state.get("councils", {})
    secretariat = review_state.get("secretariat", {})
    scope_decision = review_state.get("scope_decision", {})
    evaluation = review_state.get("evaluation", {})
    experiment = review_state.get("experiment", {})

    research_lines = merge_unique(args.research, review_research)
    if isinstance(research_gate, dict):
        summary = str(research_gate.get("summary", "")).strip()
        if summary:
            research_lines = merge_unique(research_lines, [f"Research gate summary: {summary}"])
        open_gaps = research_gate.get("open_gaps", [])
        if isinstance(open_gaps, list):
            research_lines = merge_unique(research_lines, [f"Open gap: {item}" for item in open_gaps if str(item).strip()])
    committee_lines = []
    for role in committee_summary(config):
        members = ", ".join(role["members"]) if role["members"] else "no named members"
        committee_lines.append(f"{role['label']}: {role['responsibility']} Members: {members}")
    if isinstance(councils, dict):
        council_labels = {
            "product_council": "Product Council",
            "architecture_council": "Architecture Council",
            "operator_council": "Operator Council",
        }
        for key, label in council_labels.items():
            council = councils.get(key, {})
            if not isinstance(council, dict):
                continue
            summary = str(council.get("summary", "")).strip()
            decision = str(council.get("decision", "")).strip()
            dissent = council.get("dissent", [])
            if summary:
                committee_lines.append(f"{label} summary: {summary}")
            if decision:
                committee_lines.append(f"{label} decision: {decision}")
            if isinstance(dissent, list):
                committee_lines.extend([f"{label} dissent: {item}" for item in dissent if str(item).strip()])
    committee_lines.extend(merge_unique(args.committee_feedback, review_feedback))
    committee_lines.extend(merge_unique(args.committee_decision, review_decision))

    secretariat_lines: list[str] = []
    if isinstance(secretariat, dict):
        delivery = secretariat.get("delivery_secretary", {})
        if isinstance(delivery, dict):
            summary = str(delivery.get("summary", "")).strip()
            next_action = str(delivery.get("next_action", "")).strip()
            if summary:
                secretariat_lines.append(f"Delivery Secretary summary: {summary}")
            if next_action:
                secretariat_lines.append(f"Delivery Secretary next action: {next_action}")
        audit = secretariat.get("audit_secretary", {})
        if isinstance(audit, dict):
            summary = str(audit.get("summary", "")).strip()
            decision_record = str(audit.get("decision_record", "")).strip()
            if summary:
                secretariat_lines.append(f"Audit Secretary summary: {summary}")
            if decision_record:
                secretariat_lines.append(f"Audit decision record: {decision_record}")
            open_gaps = audit.get("open_gaps", [])
            if isinstance(open_gaps, list):
                secretariat_lines.extend(prefixed_lines("Audit open gap: ", [str(item) for item in open_gaps]))
            dissent_record = audit.get("dissent_record", [])
            if isinstance(dissent_record, list):
                secretariat_lines.extend(prefixed_lines("Audit dissent: ", [str(item) for item in dissent_record]))

    scope_lines: list[str] = []
    if isinstance(scope_decision, dict):
        why_selected = str(scope_decision.get("why_selected", "")).strip()
        if why_selected:
            scope_lines.append(f"Why selected: {why_selected}")
        if isinstance(scope_decision.get("scope_in"), list):
            scope_lines.extend(prefixed_lines("Scope in: ", [str(item) for item in scope_decision.get("scope_in", [])]))
        if isinstance(scope_decision.get("scope_out"), list):
            scope_lines.extend(prefixed_lines("Scope out: ", [str(item) for item in scope_decision.get("scope_out", [])]))
        if isinstance(scope_decision.get("assumptions"), list):
            scope_lines.extend(prefixed_lines("Assumption: ", [str(item) for item in scope_decision.get("assumptions", [])]))
        if isinstance(scope_decision.get("risks"), list):
            scope_lines.extend(prefixed_lines("Risk: ", [str(item) for item in scope_decision.get("risks", [])]))
        if isinstance(scope_decision.get("required_validation"), list):
            scope_lines.extend(
                prefixed_lines("Required validation: ", [str(item) for item in scope_decision.get("required_validation", [])])
            )
        if isinstance(scope_decision.get("stop_conditions"), list):
            scope_lines.extend(prefixed_lines("Stop condition: ", [str(item) for item in scope_decision.get("stop_conditions", [])]))
        if isinstance(scope_decision.get("dissent"), list):
            scope_lines.extend(prefixed_lines("Scope dissent: ", [str(item) for item in scope_decision.get("dissent", [])]))
        next_action = str(scope_decision.get("next_action", "")).strip()
        if next_action:
            scope_lines.append(f"Next action: {next_action}")

    evaluation_lines: list[str] = []
    if isinstance(evaluation, dict) and evaluation.get("status") == "captured":
        gate = implementation_gate_status(config, evaluation)
        evaluation_lines.append(
            f"Implementation gate: {gate.get('status')} ({gate.get('mode')}, evaluator {gate.get('evaluation_result')})"
        )
        rubric_version = str(evaluation.get("rubric_version", "")).strip()
        weighted_score = evaluation.get("weighted_score")
        result = str(evaluation.get("result", "")).strip()
        summary_bits = []
        if rubric_version:
            summary_bits.append(f"rubric `{rubric_version}`")
        if weighted_score is not None:
            summary_bits.append(f"weighted score `{weighted_score}`")
        if result:
            summary_bits.append(f"result `{result}`")
        if summary_bits:
            evaluation_lines.append("Evaluator outcome: " + ", ".join(summary_bits))
        scores = evaluation.get("scores", {})
        if isinstance(scores, dict):
            score_summary = ", ".join(f"{key}={value}" for key, value in scores.items())
            if score_summary:
                evaluation_lines.append(f"Evaluator scores: {score_summary}")
        critique = evaluation.get("critique", [])
        if isinstance(critique, list):
            evaluation_lines.extend(prefixed_lines("Evaluator critique: ", [str(item) for item in critique]))
        minimum_fixes = evaluation.get("minimum_fixes_required", [])
        if isinstance(minimum_fixes, list):
            evaluation_lines.extend(prefixed_lines("Minimum fix required: ", [str(item) for item in minimum_fixes]))

    experiment_lines: list[str] = []
    if isinstance(experiment, dict) and str(experiment.get("status", "")).strip() != "not_started":
        base = experiment.get("base", {})
        candidate = experiment.get("candidate", {})
        comparison = experiment.get("comparison", {})
        promotion = experiment.get("promotion", {})
        if isinstance(base, dict):
            base_label = str(base.get("label", "")).strip()
            base_metric_name = str(base.get("metric_name", "")).strip()
            base_metric_value = base.get("metric_value")
            if base_label or base_metric_name or base_metric_value is not None:
                experiment_lines.append(
                    f"Base: {base_label or 'unknown base'}"
                    + (f", metric `{base_metric_name}`" if base_metric_name else "")
                    + (f"={base_metric_value}" if base_metric_value is not None else "")
                )
        if isinstance(candidate, dict):
            candidate_label = str(candidate.get("label", "")).strip()
            candidate_metric_name = str(candidate.get("metric_name", "")).strip()
            candidate_metric_value = candidate.get("metric_value")
            if candidate_label or candidate_metric_name or candidate_metric_value is not None:
                experiment_lines.append(
                    f"Candidate: {candidate_label or 'current candidate'}"
                    + (f", metric `{candidate_metric_name}`" if candidate_metric_name else "")
                    + (f"={candidate_metric_value}" if candidate_metric_value is not None else "")
                )
        if isinstance(comparison, dict):
            result = str(comparison.get("result", "")).strip()
            direction = str(comparison.get("direction", "")).strip()
            delta = comparison.get("delta")
            rationale = str(comparison.get("rationale", "")).strip()
            if result or direction or delta is not None or rationale:
                experiment_lines.append(
                    f"Comparison: {result or 'pending'}"
                    + (f", direction `{direction}`" if direction else "")
                    + (f", delta {delta}" if delta is not None else "")
                )
                if rationale:
                    experiment_lines.append(f"Comparison rationale: {rationale}")
        if isinstance(promotion, dict):
            decision = str(promotion.get("decision", "")).strip()
            reason = str(promotion.get("reason", "")).strip()
            next_action = str(promotion.get("next_action", "")).strip()
            if decision:
                experiment_lines.append(f"Promotion decision: {decision}")
            if reason:
                experiment_lines.append(f"Promotion reason: {reason}")
            if next_action:
                experiment_lines.append(f"Promotion next action: {next_action}")

    stop_and_escalation_lines: list[str] = []
    if isinstance(research_gate, dict):
        open_gaps = research_gate.get("open_gaps", [])
        if isinstance(open_gaps, list):
            stop_and_escalation_lines.extend(prefixed_lines("Open gap: ", [str(item) for item in open_gaps]))
    if isinstance(scope_decision, dict):
        stop_conditions = scope_decision.get("stop_conditions", [])
        if isinstance(stop_conditions, list):
            stop_and_escalation_lines.extend(prefixed_lines("Stop condition: ", [str(item) for item in stop_conditions]))
    escalation = review_state.get("escalation", {})
    if isinstance(escalation, dict):
        status = str(escalation.get("status", "")).strip()
        reason = str(escalation.get("reason", "")).strip()
        recommended_action = str(escalation.get("recommended_action", "")).strip()
        if status:
            stop_and_escalation_lines.append(f"Escalation status: {status}")
        if reason:
            stop_and_escalation_lines.append(f"Escalation reason: {reason}")
        if recommended_action:
            stop_and_escalation_lines.append(f"Escalation action: {recommended_action}")

    validation_lines = []
    for result in validation.get("results", []):
        status = "PASS" if result.get("passed") else "FAIL"
        validation_lines.append(f"- `{result.get('command')}` -> {status} (exit {result.get('exit_code')})")
    if not validation_lines:
        validation_lines = ["- No validation results were recorded."]

    evidence_sources = list(args.source)
    snapshot_path = project_data.get("snapshot_path")
    quality_path = project_data.get("quality_path")
    if review_state:
        evidence_sources.append("Durable review state: `.agent-loop/state.json`")
    if snapshot_path:
        evidence_sources.append(f"Project data snapshot: `{snapshot_path}`")
    if quality_path:
        evidence_sources.append(f"Project data quality: `{quality_path}`")
    evidence_sources = merge_unique(evidence_sources, [])

    quality_lines = list(args.quality_note)
    if quality_path:
        quality_report = load_json(workspace_root / quality_path)
        quality_lines.append(
            f"Latest quality status: `{quality_report.get('status')}`, score `{quality_report.get('overall_score')}`"
        )
        gaps = quality_report.get("blocking_gaps", [])
        if gaps:
            quality_lines.append(f"Blocking gaps: {', '.join(gaps)}")

    content = [
        f"# Task Iteration v{iteration} Report",
        "",
        f"Date: {today}",
        "",
        "## Session Progress",
        (
            f"- Release session progress: {session['completed_releases']}/{session['target_releases']}"
            if session["target_releases"] is not None
            else "- Release session progress: unbounded session"
        ),
        f"- Task iteration progress: {session['completed_iterations'] + 1}",
        (
            f"- Active release: R{release['number']} {release['title']}"
            if release["number"] is not None
            else "- Active release: no release planned"
        ),
        "",
        "## Current State Analysis",
        *bullet_lines(args.analysis, "Summarize the current repo state before this version."),
        "",
        "## Research",
        *bullet_lines(research_lines, "Summarize the repo, product, user, and architecture research completed before selecting this version."),
        "",
        "## Committee Review",
        *bullet_lines(committee_lines, "Record the requirement and review feedback from the product, architecture, and user committee."),
        "",
        "## Secretariat",
        *bullet_lines(secretariat_lines, "Record the delivery and audit secretary outcome for this iteration."),
        "",
        "## Task Goal",
        f"- Goal: {goal_label}",
        *bullet_lines(args.acceptance, "Document the acceptance criteria for this task iteration."),
        "",
        "## Scope Decision",
        *bullet_lines(scope_lines, "Record why this goal was selected, what is in scope, what is out of scope, and where the stop line sits."),
        "",
        "## Key Observations",
        *bullet_lines(args.observation, "Capture the evidence or observation that most influenced this task iteration."),
        "",
        "## Evidence Sources",
        *bullet_lines(evidence_sources, "List the repo files, commands, or generated artifacts used for this task iteration."),
        "",
        "## Data Quality",
        *bullet_lines(quality_lines, "Record the latest project-data quality status or score."),
        "",
        "## Delivered",
        *bullet_lines(args.delivered, "List the concrete changes delivered in this task iteration."),
        "",
        "## Evaluation Readiness",
        *bullet_lines(evaluation_lines, "Record the evaluator outcome, weighted score, and minimum fixes when available."),
        "",
        "## Experiment",
        *bullet_lines(
            experiment_lines,
            "No experiment comparison was captured for this goal.",
        ),
        "",
        "## Stop And Escalation",
        *bullet_lines(
            stop_and_escalation_lines,
            "Record open gaps, stop conditions, and escalation status so a later operator can see why the loop would stop or escalate.",
        ),
        "",
        "## Full Validation",
        *validation_lines,
        "",
        "## Reflection",
        *bullet_lines(merge_unique(args.reflection, review_reflection), "Reflect on requirement clarity and architectural impact."),
        "",
        "## Proposed Next Goal",
        *bullet_lines(args.next_goal, "Propose the next highest-value task inside the current release or the next release theme."),
        "",
    ]
    report_path.write_text(translate_report_text("\n".join(content)), encoding="utf-8")

    state = load_state(workspace_root)
    state["draft_iteration"] = iteration
    state["draft_report"] = relpath(report_path, workspace_root)
    state["draft_goal"] = goal
    state["status"] = "report_written"
    save_state(workspace_root, state)
    append_usage_log(
        workspace_root,
        config,
        "report_written",
        {
            "iteration": iteration,
            "report": relpath(report_path, workspace_root),
            "goal": goal_label,
            "goal_id": goal.get("id") if isinstance(goal, dict) else "",
        },
        target_root=target_root,
    )

    cli_info(f"任务报告已写入：{report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
