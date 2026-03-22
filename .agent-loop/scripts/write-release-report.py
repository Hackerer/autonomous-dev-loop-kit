#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from common import (
    append_usage_log,
    cli_info,
    LoopError,
    active_release,
    is_placeholder_text,
    load_config,
    load_state,
    relpath,
    release_reporting_path,
    release_summary,
    require_green_validation,
    resolve_execution_roots,
    save_state,
    session_summary,
)


def section_map(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("## "):
            current = raw_line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(raw_line)
    return sections


def bulletize(lines: list[str], fallback: str) -> list[str]:
    values = [line for line in lines if line.strip()]
    if not values:
        return [f"- {fallback}"]
    bullets: list[str] = []
    for line in values:
        if line.startswith("- "):
            bullets.append(line)
        else:
            bullets.append(f"- {line}")
    return bullets


def optional_bulletize(lines: list[str]) -> list[str]:
    values = [line for line in lines if line.strip()]
    if not values:
        return []
    bullets: list[str] = []
    for line in values:
        if line.startswith("- "):
            bullets.append(line)
        else:
            bullets.append(f"- {line}")
    return bullets


def translate_release_report_text(text: str) -> str:
    replacements = [
        ("# R", "# R"),
        ("Release Report", "发布报告"),
        ("Date:", "日期："),
        ("## Release Definition", "## 发布定义"),
        ("## PM Release Brief", "## 产品发布简报"),
        ("## Experiment Baseline", "## 实验基线"),
        ("## Included Scope", "## 包含范围"),
        ("## Release Scope Boundary", "## 发布范围边界"),
        ("## Requirement Delivery", "## 需求交付"),
        ("## Release Acceptance", "## 发布验收"),
        ("## Technical Validation", "## 技术验证"),
        ("## Detailed Output", "## 详细输出"),
        ("## Task Traceability", "## 任务可追溯性"),
        ("## Session Progress", "## 会话进度"),
        ("## Next Release Recommendation", "## 下一发布建议"),
        ("Release:", "发布："),
        ("Title:", "标题："),
        ("Archetype:", "原型："),
        ("Objective:", "目标："),
        ("Target user value:", "目标用户价值："),
        ("Why now:", "为何现在："),
        ("Packaging rationale:", "打包理由："),
        ("Launch story:", "发布故事："),
        ("Packaging signal:", "打包信号："),
        ("Base release:", "基线发布："),
        ("Base title:", "基线标题："),
        ("Metric:", "指标："),
        ("Promotion rule:", "晋级规则："),
        ("In scope:", "范围内："),
        ("Out of scope:", "范围外："),
        ("Deferred:", "延后："),
        ("Releases completed after publish:", "发布后已完成的发布数："),
        ("Task iterations included:", "包含的任务迭代数："),
        ("candidate metric", "候选指标"),
        ("baseline metric", "基线指标"),
        ("experiment decision", "实验决策"),
        ("Document why this bundled release exists and what user-facing package it represents.", "请说明这个发布包为什么存在，以及它代表了什么面向用户的产品包。"),
        ("Release:", "发布："),
        ("Task iterations included:", "包含的任务迭代数："),
        ("Record the PM release objective, user value, why-now logic, packaging rationale, and launch story.", "请记录产品发布目标、用户价值、为何现在、打包理由和发布故事。"),
        ("Record the strongest signals that justify this release bundle.", "请记录最能支持该发布包的信号。"),
        ("Document the base version and metric used to judge whether this release should be promoted.", "请记录用于判断该发布是否应晋级的基线版本和指标。"),
        ("List the bundled goals included in this release.", "请列出本次发布包含的目标。"),
        ("Record the release-level in-scope items.", "请记录发布层面的范围内项。"),
        ("Record the release-level out-of-scope items.", "请记录发布层面的范围外项。"),
        ("Record the release-level acceptance criteria for this bundled version.", "请记录该发布包的验收标准。"),
        ("Record the validation results that prove this release is technically sound.", "请记录证明该发布技术上可靠的验证结果。"),
        ("Explain the notable outputs, operator-visible behavior, and architectural consequences of this release.", "请说明本次发布的显著输出、运维可见行为和架构影响。"),
        ("Link each task iteration report that was bundled into this release.", "请链接本次发布打包的每个任务迭代报告。"),
        ("Document the next bundled release theme or reason to stop.", "请记录下一次发布包的主题，或说明停止原因。"),
        ("No active release exists. Plan one first with", "当前没有活动发布。请先运行"),
        ("The active release still has incomplete goals. Finish and publish each task iteration before writing the release report.", "当前发布仍有未完成目标。请先完成并发布每个任务迭代，再生成发布报告。"),
    ]
    for src, dst in replacements:
        text = text.replace(src, dst)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="生成汇总多个任务迭代的发布报告。")
    parser.add_argument("--summary", action="append", default=[], help="发布级总结条目。")
    parser.add_argument("--output-note", action="append", default=[], help="发布的详细输出条目。")
    parser.add_argument("--next-release", action="append", default=[], help="下一次发布建议条目。")
    args = parser.parse_args()

    kit_root, target_root, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    cli_info("正在生成发布报告。")
    release = release_summary(state)
    require_green_validation(state)

    if release["status"] in {"not_planned", "published"} or release["number"] is None:
        raise LoopError("当前没有可用的发布。请先运行 `python3 .agent-loop/scripts/plan-release.py`。")
    if release["remaining_goal_ids"]:
        raise LoopError(
            "当前发布仍有未完成目标。请先完成并发布每个任务迭代，再生成发布报告。"
        )

    release_number = int(release["number"])
    report_path = release_reporting_path(workspace_root, config, release_number)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().date().isoformat()
    session = session_summary(state)

    brief = release.get("brief", {}) if isinstance(release.get("brief"), dict) else {}
    baseline = brief.get("baseline_release", {}) if isinstance(brief.get("baseline_release"), dict) else {}
    task_iterations = []
    for item in release.get("task_iterations", []):
        if isinstance(item, dict):
            task_iterations.append(item)

    delivered_lines: list[str] = []
    validation_lines: list[str] = []
    output_lines: list[str] = list(args.output_note)
    task_trace_lines: list[str] = []
    for item in task_iterations:
        task_label = f"v{item.get('iteration')} {item.get('goal', '')}".strip()
        report_rel = str(item.get("report", "")).strip()
        task_trace_lines.append(f"- {task_label} -> `{report_rel}`")
        if report_rel:
            sections = section_map(workspace_root / report_rel)
            delivered_lines.extend(
                [
                    f"{task_label}: {line[2:]}"
                    for line in sections.get("Delivered", [])
                    if line.startswith("- ") and not is_placeholder_text(line[2:])
                ]
            )
            validation_lines.extend([f"{task_label}: {line[2:]}" for line in sections.get("Full Validation", []) if line.startswith("- ")])
            output_lines.extend(
                [
                    f"{task_label}: {line[2:]}"
                    for line in sections.get("Key Observations", [])
                    if line.startswith("- ") and not is_placeholder_text(line[2:])
                ]
            )
        metric_value = item.get("candidate_metric_value")
        if metric_value is not None:
            output_lines.append(f"{task_label}: candidate metric {metric_value}")
        baseline_metric_value = item.get("baseline_metric_value")
        if baseline_metric_value is not None:
            output_lines.append(f"{task_label}: baseline metric {baseline_metric_value}")
        experiment_decision = str(item.get("experiment_decision", "")).strip()
        if experiment_decision:
            output_lines.append(f"{task_label}: experiment decision {experiment_decision}")

    content = [
        f"# R{release_number} Release Report",
        "",
        f"Date: {today}",
        "",
        "## Release Definition",
        f"- Release: R{release_number}",
        f"- Title: {release['title'] or f'Release {release_number}'}",
        *bulletize(args.summary or [release["summary"]], "Document why this bundled release exists and what user-facing package it represents."),
        "",
        "## PM Release Brief",
        *bulletize(
            [
                f"Archetype: {brief.get('archetype', '')}",
                f"Objective: {brief.get('objective', '')}",
                f"Target user value: {brief.get('target_user_value', '')}",
                f"Why now: {brief.get('why_now', '')}",
                f"Packaging rationale: {brief.get('packaging_rationale', '')}",
                f"Launch story: {brief.get('launch_story', '')}",
            ],
            "Record the PM release objective, user value, why-now logic, packaging rationale, and launch story.",
        ),
        *bulletize([f"Packaging signal: {item}" for item in brief.get("packaging_signals", [])], "Record the strongest signals that justify this release bundle."),
        "",
        "## Experiment Baseline",
        *bulletize(
            [
                (
                    f"Base release: R{baseline.get('number')}"
                    if baseline.get("number") is not None
                    else f"Base release: {baseline.get('title', '') or 'none recorded'}"
                ),
                f"Base title: {baseline.get('title', '')}",
                f"Metric: {baseline.get('metric_name', '')} = {baseline.get('metric_value')}",
                f"Promotion rule: {brief.get('promotion_rule', '')}",
            ],
            "Document the base version and metric used to judge whether this release should be promoted.",
        ),
        "",
        "## Included Scope",
        *bulletize(release["goal_titles"], "List the bundled goals included in this release."),
        "",
        "## Release Scope Boundary",
        *bulletize([f"In scope: {item}" for item in brief.get("scope_in", [])], "Record the release-level in-scope items."),
        *bulletize([f"Out of scope: {item}" for item in brief.get("scope_out", [])], "Record the release-level out-of-scope items."),
        *optional_bulletize([f"Deferred: {item}" for item in brief.get("deferred_items", [])]),
        "",
        "## Requirement Delivery",
        *bulletize(delivered_lines, "Summarize what this release delivered across the included task iterations."),
        "",
        "## Release Acceptance",
        *bulletize(brief.get("release_acceptance", []), "Record the release-level acceptance criteria for this bundled version."),
        "",
        "## Technical Validation",
        *bulletize(validation_lines, "Record the validation results that prove this release is technically sound."),
        "",
        "## Detailed Output",
        *bulletize(output_lines, "Explain the notable outputs, operator-visible behavior, and architectural consequences of this release."),
        "",
        "## Task Traceability",
        *bulletize(task_trace_lines, "Link each task iteration report that was bundled into this release."),
        "",
        "## Session Progress",
        (
            f"- Releases completed after publish: {session['completed_releases'] + 1}/{session['target_releases']}"
            if session["target_releases"] is not None
            else "- Releases completed after publish: unbounded session"
        ),
        f"- Task iterations included: {len(task_iterations)}",
        "",
        "## Next Release Recommendation",
        *bulletize(args.next_release, "Document the next bundled release theme or reason to stop."),
        "",
    ]

    report_path.write_text(translate_release_report_text("\n".join(content)), encoding="utf-8")
    state["draft_release_report"] = relpath(report_path, workspace_root)
    state["status"] = "release_report_written"
    save_state(workspace_root, state)
    append_usage_log(
        workspace_root,
        config,
        "release_report_written",
        {
            "release_number": release_number,
            "report": relpath(report_path, workspace_root),
            "task_iterations": len(task_iterations),
        },
        target_root=target_root,
    )
    cli_info(f"发布报告已写入：{report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
