#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import append_usage_log, LoopError, load_config, load_state, planning_config, resolve_execution_roots, save_state


def main() -> int:
    parser = argparse.ArgumentParser(description="在不重置进度的情况下延长当前自治会话。")
    parser.add_argument("--iterations", type=int, help="为活动会话设置新的总发布次数目标。")
    parser.add_argument("--add", type=int, help="在当前会话目标上增加这么多次汇总发布。")
    args = parser.parse_args()

    if args.iterations is None and args.add is None:
        raise LoopError("请提供 --iterations 或 --add 之一。")
    if args.iterations is not None and args.add is not None:
        raise LoopError("只能使用 --iterations 或 --add 其一，不能同时使用。")
    if args.add is not None and args.add <= 0:
        raise LoopError("--add 必须是正整数。")
    if args.iterations is not None and args.iterations <= 0:
        raise LoopError("--iterations 必须是正整数。")

    kit_root, target_root, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    planning = planning_config(config)
    max_allowed = planning.get("max_releases_per_session", planning.get("max_iterations_per_session"))

    session = state.get("session", {})
    if not isinstance(session, dict) or session.get("status") not in {"active", "completed"}:
        raise LoopError("没有可继续的已配置会话。请先运行 `python3 .agent-loop/scripts/set-loop-session.py --iterations N`。")

    completed = int(session.get("completed_releases", session.get("completed_iterations", 0)) or 0)
    current_target = session.get("target_releases", session.get("target_iterations"))
    if current_target is None:
        raise LoopError("当前会话没有可延长的 target_releases 值。")

    next_target = int(args.iterations) if args.iterations is not None else int(current_target) + int(args.add)
    if next_target <= completed:
        raise LoopError(f"新的会话目标必须大于已完成进度（{completed}）。")
    if max_allowed is not None and next_target > int(max_allowed):
        raise LoopError(
            f"请求的总发布数为 {next_target}，但配置 planning.max_releases_per_session 只允许 {int(max_allowed)}。"
        )

    state["session"]["target_releases"] = next_target
    state["session"]["status"] = "active"
    state["session"]["ended_at"] = None
    if state.get("status") == "session_completed":
        state["status"] = "published"
    save_state(workspace_root, state)
    append_usage_log(
        workspace_root,
        config,
        "session_extended",
        {
            "session_id": state.get("session", {}).get("id"),
            "completed_releases": completed,
            "target_releases": next_target,
        },
        target_root=target_root,
    )

    print(f"已将自治循环会话延长到总共 {next_target} 次发布（已完成 {completed} 次）。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
