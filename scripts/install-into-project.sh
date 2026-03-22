#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR=""

usage() {
  cat <<EOF
Usage: $(basename "$0") --target PATH [options]

Register a target project for this kit without copying kit assets into the target.

Options:
  --target PATH           Target project root directory.
  -h, --help              Show this help.
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
        echo "Missing value for --target" >&2
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
      echo "Unknown argument: $1" >&2
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

printf 'Project installer finished for %s\n' "$TARGET_DIR"
cat <<EOF
This installer does not write kit assets into the target project by default.
It only records the target path inside the kit workspace project folder:

  ${PROJECT_WORKSPACE_ROOT}/.agent-loop/data/usage-log.jsonl
EOF

if [[ -n "$REGISTERED_WORKSPACE_ROOT" ]]; then
cat <<EOF
The project registry entry is also updated at:

  ${REGISTERED_WORKSPACE_ROOT}
EOF
else
cat <<EOF
Registry updates were skipped for this installation.
EOF
fi
