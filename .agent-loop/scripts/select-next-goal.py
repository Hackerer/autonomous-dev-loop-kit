#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import (
    cli_info,
    active_release_goal_ids,
    active_release,
    LoopError,
    goal_selection_blockers,
    goal_title,
    load_backlog,
    load_config,
    load_json,
    load_state,
    release_planning_config,
    release_summary,
    require_session_capacity,
    resolve_execution_roots,
    save_state,
    session_summary,
    utc_now,
)


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DATA_KEYWORDS = ("data", "evidence", "quality", "tool", "validation", "collect", "score", "state")


def load_quality_context(root: Path, state: dict) -> tuple[str | None, list[str]]:
    project_data = state.get("project_data", {})
    quality_path = project_data.get("quality_path")
    if not quality_path:
        return project_data.get("last_quality_status"), []
    quality_file = root / quality_path
    if not quality_file.exists():
        return project_data.get("last_quality_status"), []
    quality = load_json(quality_file)
    return quality.get("status"), quality.get("blocking_gaps", [])


def gap_priority(item: dict, quality_status: str | None, gaps: list[str]) -> int:
    if quality_status in {None, "ready"}:
        return 0
    haystack = " ".join(
        [
            str(item.get("id", "")),
            str(item.get("title", "")),
            str(item.get("notes", "")),
            " ".join(item.get("acceptance", [])),
        ]
    ).lower()

    keyword_hits = sum(1 for keyword in DATA_KEYWORDS if keyword in haystack)
    gap_hits = 0
    for gap in gaps:
        for token in gap.lower().split():
            if token in {"missing", "signals"}:
                continue
            if token in haystack:
                gap_hits += 1

    if keyword_hits or gap_hits:
        return -1 * (keyword_hits + gap_hits)
    return 0


def pick_goal(root: Path, backlog: list[dict], state: dict) -> dict:
    release_goal_ids = set(active_release_goal_ids(state))
    if release_goal_ids:
        pending = [
            item
            for item in backlog
            if item.get("status", "pending") == "pending" and str(item.get("id", "")) in release_goal_ids
        ]
    else:
        pending = [item for item in backlog if item.get("status", "pending") == "pending"]
    if not pending:
        raise LoopError("没有剩余的待处理待办项。")
    quality_status, gaps = load_quality_context(root, state)
    pending.sort(
        key=lambda item: (
            PRIORITY_ORDER.get(item.get("priority", "medium"), 99),
            gap_priority(item, quality_status, gaps),
            item.get("id", ""),
        )
    )
    return pending[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="为自治循环选择下一个已聚焦的目标。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整选中目标。")
    args = parser.parse_args()

    kit_root, _, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    backlog = load_backlog(workspace_root)
    state = load_state(workspace_root)
    session = require_session_capacity(config, state)
    release_cfg = release_planning_config(config)
    release = release_summary(state)
    if release_cfg["require_release_plan"] and release["status"] in {"not_planned", "published"}:
        raise LoopError("当前没有活动发布计划。请先运行 `python3 .agent-loop/scripts/plan-release.py` 再选择下一个任务目标。")
    if release["goal_ids"] and not release["remaining_goal_ids"]:
        raise LoopError(
            "当前发布已完成所有计划目标。请先运行 `python3 .agent-loop/scripts/write-release-report.py` 和 "
            "`python3 .agent-loop/scripts/publish-release.py` 写出并发布汇总发布，再选择下一次发布中的目标。"
        )
    quality_status, gaps = load_quality_context(workspace_root, state)
    blockers = goal_selection_blockers(config, state, quality_status, gaps)
    if blockers:
        raise LoopError(
            "目标选择被阻塞，因为还需要更多上下文：\n- "
            + "\n- ".join(blockers)
            + "\n请刷新项目数据或补充最新研究结论，然后重新运行 `python3 .agent-loop/scripts/select-next-goal.py`。"
        )
    selected = pick_goal(workspace_root, backlog, state)

    state["current_goal"] = {
        "id": selected.get("id"),
        "title": selected.get("title"),
        "priority": selected.get("priority", "medium"),
        "selected_at": utc_now(),
        "source": ".agent-loop/backlog.json",
    }
    state["status"] = "goal_selected"
    save_state(workspace_root, state)

    if args.json:
        print(json.dumps(selected, ensure_ascii=True, indent=2))
    else:
        progress = session_summary(state)
        suffix = ""
        release_bits: list[str] = []
        if progress["target_releases"] is not None:
            release_bits.append(f"release {progress['completed_releases'] + 1}/{progress['target_releases']}")
        if release["number"] is not None and release["goal_ids"]:
            completed = len(release["completed_goal_ids"])
            total = len(release["goal_ids"])
            release_bits.append(f"tasks {completed + 1}/{total} in R{release['number']}")
        if release_bits:
            suffix = f" ({', '.join(release_bits)})"
        cli_info(f"已选择目标：{goal_title(selected)}{suffix}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
