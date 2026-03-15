#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR=""
OVERWRITE_CONFIG=0
OVERWRITE_STATE=0
OVERWRITE_BACKLOG=0
OVERWRITE_TOP_LEVEL=0

usage() {
  cat <<EOF
Usage: $(basename "$0") --target PATH [options]

Install this kit into a target project root without manually copying files.

Options:
  --target PATH           Target project root directory.
  --overwrite-config      Replace the target .agent-loop/config.json.
  --overwrite-state       Replace the target .agent-loop/state.json.
  --overwrite-backlog     Replace the target .agent-loop/backlog.json.
  --overwrite-top-level   Replace AGENTS.md, CLAUDE.md, and PLANS.md if they exist.
  -h, --help              Show this help.
EOF
}

copy_file() {
  local source="$1"
  local destination="$2"
  local overwrite="$3"
  local label="$4"

  mkdir -p "$(dirname "$destination")"
  if [[ -e "$destination" && "$overwrite" -ne 1 ]]; then
    printf 'Preserved existing %s at %s\n' "$label" "$destination"
    return
  fi

  cp "$source" "$destination"
  printf 'Installed %s at %s\n' "$label" "$destination"
}

sync_dir() {
  local relative_path="$1"
  local destination="${TARGET_DIR}/${relative_path}"

  mkdir -p "$destination"
  rsync -a \
    --exclude '.DS_Store' \
    "${ROOT}/${relative_path}/" "${destination}/"
  printf 'Synced %s into %s\n' "$relative_path" "$destination"
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
    --overwrite-config)
      OVERWRITE_CONFIG=1
      shift
      ;;
    --overwrite-state)
      OVERWRITE_STATE=1
      shift
      ;;
    --overwrite-backlog)
      OVERWRITE_BACKLOG=1
      shift
      ;;
    --overwrite-top-level)
      OVERWRITE_TOP_LEVEL=1
      shift
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

mkdir -p "$TARGET_DIR"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

sync_dir ".agents"
sync_dir ".claude"
sync_dir ".agent-loop/scripts"
sync_dir ".agent-loop/references"
sync_dir ".agent-loop/templates"

mkdir -p "${TARGET_DIR}/.agent-loop/data" "${TARGET_DIR}/docs/reports"

copy_file "${ROOT}/AGENTS.md" "${TARGET_DIR}/AGENTS.md" "$OVERWRITE_TOP_LEVEL" "AGENTS.md"
copy_file "${ROOT}/CLAUDE.md" "${TARGET_DIR}/CLAUDE.md" "$OVERWRITE_TOP_LEVEL" "CLAUDE.md"
copy_file "${ROOT}/PLANS.md" "${TARGET_DIR}/PLANS.md" "$OVERWRITE_TOP_LEVEL" "PLANS.md"
copy_file "${ROOT}/.agent-loop/config.json" "${TARGET_DIR}/.agent-loop/config.json" "$OVERWRITE_CONFIG" ".agent-loop/config.json"
copy_file "${ROOT}/.agent-loop/state.json" "${TARGET_DIR}/.agent-loop/state.json" "$OVERWRITE_STATE" ".agent-loop/state.json"
copy_file "${ROOT}/.agent-loop/backlog.json" "${TARGET_DIR}/.agent-loop/backlog.json" "$OVERWRITE_BACKLOG" ".agent-loop/backlog.json"

printf 'Project installer finished for %s\n' "$TARGET_DIR"
cat <<EOF
Next bootstrap steps:
  1. Replace placeholder validation commands in ${TARGET_DIR}/.agent-loop/config.json if needed.
  2. Collect and score project data:
     python3 .agent-loop/scripts/collect-project-data.py
     python3 .agent-loop/scripts/score-data-quality.py
  3. Render the committee brief and do research:
     python3 .agent-loop/scripts/render-committee.py
  4. If research still lacks context, record:
     python3 .agent-loop/scripts/capture-review.py --research-status need_more_context --research-summary "..." --open-gap "..."
  5. After goal selection, render evaluator input and confirm readiness:
     python3 .agent-loop/scripts/render-evaluator-brief.py
     python3 .agent-loop/scripts/assert-implementation-readiness.py
EOF
