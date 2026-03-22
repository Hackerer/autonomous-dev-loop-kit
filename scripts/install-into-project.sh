#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR=""

usage() {
  cat <<EOF
Usage: $(basename "$0") --target PATH [options]

为此 kit 注册一个目标项目，不会把 kit 资产复制到目标目录。

Options:
  --target PATH           目标项目根目录。
  -h, --help              显示帮助。
EOF
}

project_workspace_root() {
  python3 - "$ROOT" "$TARGET_DIR" <<'PY'
from pathlib import Path
import sys

kit = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
import sys
sys.path.insert(0, str(kit / ".agent-loop" / "scripts"))
from common import project_workspace_root
print(project_workspace_root(kit, target))
PY
}

register_project_workspace() {
  python3 - "$ROOT" "$TARGET_DIR" <<'PY'
from pathlib import Path
import sys

kit = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
import sys
sys.path.insert(0, str(kit / ".agent-loop" / "scripts"))
from common import register_project_workspace
print(register_project_workspace(kit, target))
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 ]]; then
        echo "--target 缺少值" >&2
        exit 1
      fi
      TARGET_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$TARGET_DIR" ]]; then
  usage >&2
  exit 1
fi

TARGET_DIR="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$TARGET_DIR")"
PROJECT_WORKSPACE_ROOT="$(project_workspace_root)"
INSTALL_MODE="no-copy"
USAGE_LOG_ROOT="${PROJECT_WORKSPACE_ROOT}"

REGISTERED_WORKSPACE_ROOT=""
if [[ "${AUTONOMOUS_DEV_LOOP_SKIP_REGISTRY:-0}" != "1" ]]; then
  REGISTERED_WORKSPACE_ROOT="$(register_project_workspace)"
fi

python3 "${ROOT}/.agent-loop/scripts/record-usage-event.py" \
  --repo-root "${USAGE_LOG_ROOT}" \
  --target-root "${TARGET_DIR}" \
  --event kit_installed \
  --field "source_repo=${ROOT}" \
  --field "target_repo=${TARGET_DIR}" \
  --field "mode=${INSTALL_MODE}" \
  >/dev/null

printf '项目注册完成：%s\n' "$TARGET_DIR"
cat <<EOF
此安装器默认不会向目标项目写入 kit 资产。
它只会把目标路径记录到 kit 工作区中的项目目录：

  ${PROJECT_WORKSPACE_ROOT}/.agent-loop/data/usage-log.jsonl
EOF

if [[ -n "$REGISTERED_WORKSPACE_ROOT" ]]; then
cat <<EOF
项目注册表也已更新到：

  ${REGISTERED_WORKSPACE_ROOT}
EOF
else
cat <<EOF
本次安装已跳过注册表更新。
EOF
fi
