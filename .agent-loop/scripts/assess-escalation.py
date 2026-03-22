#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import assess_escalation, load_config, load_state, resolve_execution_roots, save_state


def main() -> int:
    parser = argparse.ArgumentParser(description="评估当前循环状态是否应继续观察或升级重复失败。")
    parser.add_argument("--apply", action="store_true", help="将评估结果写入 review_state.escalation。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出评估结果。")
    args = parser.parse_args()

    kit_root, _, workspace_root = resolve_execution_roots()
    config = load_config(kit_root)
    state = load_state(workspace_root)
    assessment = assess_escalation(config, state)

    if args.apply:
        review_state = state.get("review_state", {})
        if not isinstance(review_state, dict):
            review_state = {}
        review_state["escalation"] = assessment
        state["review_state"] = review_state
        save_state(workspace_root, state)

    if args.json:
        print(json.dumps(assessment, ensure_ascii=True, indent=2))
    else:
        print(f"升级状态：{assessment['status']}")
        if assessment["reason"]:
            print(f"原因：{assessment['reason']}")
        if assessment["recommended_action"]:
            print(f"建议动作：{assessment['recommended_action']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - defensive CLI exit
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
