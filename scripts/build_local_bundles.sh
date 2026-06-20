#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
elif [[ -x "$repo_root/.venv/Scripts/python.exe" ]]; then
  python_bin="$repo_root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
else
  python_bin="python"
fi

exec "$python_bin" -m desi_rv_variables.cli build-local-bundles \
  --project-root "$repo_root" \
  "$@"
