#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_BUNDLE_NAME="$(basename "$ROOT")"

CODEX_DIR="${HOME}/.codex/skills"
CLAUDE_DIR="${HOME}/.claude/skills"

BUNDLE_NAME="$DEFAULT_BUNDLE_NAME"
INSTALL_CODEX=1
INSTALL_CLAUDE=1

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Install this kit into local Codex and Claude Code user skill directories.

Options:
  --name NAME      Override the installed bundle directory name.
  --codex-only     Install only into ~/.codex/skills.
  --claude-only    Install only into ~/.claude/skills.
  -h, --help       Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --name" >&2
        exit 1
      fi
      BUNDLE_NAME="$2"
      shift 2
      ;;
    --codex-only)
      INSTALL_CLAUDE=0
      shift
      ;;
    --claude-only)
      INSTALL_CODEX=0
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

if [[ "$INSTALL_CODEX" -eq 0 && "$INSTALL_CLAUDE" -eq 0 ]]; then
  echo "Nothing to install. Choose at least one target." >&2
  exit 1
fi

sync_bundle() {
  local target_root="$1"
  local label="$2"
  local target_dir="${target_root}/${BUNDLE_NAME}"

  mkdir -p "$target_root"
  rsync -a \
    --exclude '.git' \
    --exclude '.DS_Store' \
    --exclude '.agent-loop/data/*.generated.json' \
    "${ROOT}/" "$target_dir/"

  printf 'Installed %s bundle to %s\n' "$label" "$target_dir"
}

if [[ "$INSTALL_CODEX" -eq 1 ]]; then
  sync_bundle "$CODEX_DIR" "Codex"
fi

if [[ "$INSTALL_CLAUDE" -eq 1 ]]; then
  sync_bundle "$CLAUDE_DIR" "Claude Code"
fi
