#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import append_usage_log, default_state, LoopError, load_config, load_state, planning_config, resolve_execution_roots, save_state, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="记录当前自治会话允许发布的次数。")
    parser.add_argument("--iterations", type=int, required=True, help="本次自治会话最多可发布多少个汇总版本。")
    args = parser.parse_args()

    if args.iterations <= 0:
        raise LoopError("--iterations 必须是正整数。")

    kit_root, target_root, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    planning = planning_config(config)
    max_allowed = planning.get("max_releases_per_session", planning.get("max_iterations_per_session"))
    if max_allowed is not None and args.iterations > int(max_allowed):
        raise LoopError(
            f"请求了 {args.iterations} 次发布，但配置 planning.max_releases_per_session 只允许 {int(max_allowed)} 次。"
        )
    session_started_at = utc_now()
    session_id = f"session-{session_started_at.replace(':', '').replace('-', '').replace('T', '-').replace('Z', '')}"

    state["session"] = {
        "id": session_id,
        "status": "active",
        "target_releases": int(args.iterations),
        "completed_releases": 0,
        "target_iterations": None,
        "completed_iterations": 0,
        "started_at": session_started_at,
        "ended_at": None,
    }
    state["status"] = "session_configured"
    state["current_goal"] = None
    state["release"] = default_state()["release"]
    state["draft_iteration"] = None
    state["draft_report"] = None
    state["draft_release_report"] = None
    state["draft_goal"] = None
    state["review_state"] = default_state()["review_state"]
    state["consecutive_failures"] = 0
    save_state(workspace_root, state)
    append_usage_log(
        workspace_root,
        config,
        "session_started",
        {
            "session_id": session_id,
            "target_releases": int(args.iterations),
        },
        target_root=target_root,
    )

    print(f"已配置自治循环会话，可发布 {args.iterations} 个汇总版本。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
