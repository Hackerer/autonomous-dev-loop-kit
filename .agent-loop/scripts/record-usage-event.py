#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import append_usage_log, cli_info, kit_root, load_config, LoopError, project_root


def parse_fields(items: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise LoopError(f"--field 值无效 '{item}'。应为 key=value。")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise LoopError(f"--field 值无效 '{item}'。必须提供字段名。")
        fields[key] = value
    return fields


def main() -> int:
    parser = argparse.ArgumentParser(description="记录当前或目标仓库的一条轻量使用事件。")
    parser.add_argument("--event", required=True, help="要记录的使用事件类型。")
    parser.add_argument("--repo-root", help="显式工作区根目录，默认使用 kit 工作区根目录。")
    parser.add_argument("--target-root", help="显式目标项目根目录，会写入使用载荷。")
    parser.add_argument("--field", action="append", default=[], help="额外载荷字段，格式为 key=value。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出事件路径和载荷。")
    args = parser.parse_args()

    workspace_root = Path(args.repo_root).resolve() if args.repo_root else kit_root()
    target_root = Path(args.target_root).resolve() if args.target_root else project_root()
    config = load_config(kit_root())
    payload = parse_fields(list(args.field))
    log_path = append_usage_log(workspace_root, config, args.event, payload, target_root=target_root)
    result = {
        "event": args.event,
        "repo_root": str(workspace_root),
        "target_root": str(target_root),
        "log_path": str(log_path) if log_path else "",
        "payload": payload,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        cli_info(f"已记录使用事件 '{args.event}'，位置：{result['log_path']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1)
